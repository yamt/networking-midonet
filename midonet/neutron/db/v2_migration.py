# Copyright (C) 2017 Midokura SARL.
# All rights reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import functools

from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import uuidutils

from neutron_lib import context as ctx

from neutron.db import api as db_api
from neutron.db.models import portbinding
from neutron.db import models_v2
from neutron.db import segments_db
from neutron.objects import network as network_obj
from neutron.plugins.ml2 import models as ml2_models

from midonet.neutron.db import port_binding_db
from midonet.neutron.db import provider_network_db


# midonet v2 port binding:
#    midonet_port_bindings (port_binding_db.PortBindingInfo)
#    portbindingports (portbinding.PortBindingPort)

# ml2 port binding:
#    ml2_port_bindings (ml2_models.PortBinding)
#    ml2_port_binding_levels (ml2_models.PortBindingLevel)
#    ml2_distributed_port_bindings (ml2_models.DistributedPortBinding)

# midonet v2 segments:
#    midonet_network_bindings (provider_network_db.NetworkBinding)

# ml2 segments:
#    networksegments (neutron.db.models.segment.NetworkSegment)


LOG = logging.getLogger(__name__)


def log_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        LOG.info('Calling %(func)s with %(args)s %(kwargs)s', {
            'func': func.__name__,
            'args': args,
            'kwargs': kwargs,
        })
        return func(*args, **kwargs)

    return wrapper


@log_calls
def add_segment(context, network_id, network_type):
    # NOTE(yamamoto): The code fragment is a modified copy of segments_db.py.
    # We don't want to make callback notifications.
    netseg_obj = network_obj.NetworkSegment(
        context, id=uuidutils.generate_uuid(),
        network_id=network_id,
        network_type=network_type,
        physical_network=None,
        segmentation_id=None,
        segment_index=0,
        is_dynamic=False)
    netseg_obj.create()


@log_calls
def add_binding_bound(context, port_id, segment_id, host, interface_name):
    context.session.add(ml2_models.PortBindingLevel(
        port_id=port_id,
        host=host,
        level=0,
        driver='midonet',
        segment_id=segment_id))
    profile = {}
    if interface_name is not None:
        profile['interface_name'] = interface_name
    context.session.add(ml2_models.PortBinding(
        port_id=port_id,
        vif_type='midonet',
        vnic_type='normal',
        profile=jsonutils.dumps(profile),
        vif_details=jsonutils.dumps({'port_filter': True}),
        status='ACTIVE'))


@log_calls
def add_binding_unbound(context, port_id):
    # ml2 add_port_binding equiv
    context.session.add(ml2_models.PortBinding(
        port_id=port_id,
        vif_type='unbound',
        vnic_type='normal',
        profile='',
        vif_details='',
        status='ACTIVE'))


@log_calls
def migrate():
    # Migrate db tables from v2 to ML2
    # NOTE(yamamoto): This would bump revisions of affected resources.

    context = ctx.get_admin_context()
    with db_api.context_manager.writer.using(context):
        # Lock all old rows for the case of multiple neutron servers.
        old_segments = context.session.query(
            provider_network_db.NetworkBinding).with_for_update().all()
        old_host_bindings = context.session.query(
            portbinding.PortBindingPort).with_for_update().all()
        old_interface_bindings = context.session.query(
            port_binding_db.PortBindingInfo).with_for_update().all()

        # Migrate network segments
        segments = {}
        uplink_network_ids = [seg.network_id for seg in old_segments]
        for network_id in uplink_network_ids:
            segments[network_id] = add_segment(context,
                network_id=network_id, network_type="uplink")
        networks = context.session.query(models_v2.Network).all()
        for net in networks:
            if net.id not in uplink_network_ids:
                segments[network_id] = add_segment(context,
                    network_id=net.id, network_type="midonet")

        # Migrate port bindings
        port_host = {}
        for binding in old_host_bindings:
            port_host[binding.port_id] = binding.host
        port_interface = {}
        for binding in old_interface_bindings:
            port_interface[binding.port_id] = binding.interface_name
        for port in context.session.query(models_v2.Port).all():
            port_id = port.id
            if port_id in port_host:
                add_binding_bound(context, port_id, segments[port.network_id],
                    port_host[port_id], port_interface.get(port_id))
            else:
                add_binding_unbound(context, port_id)

        # Delete no longer used rows
        map(context.session.delete, old_segments)
        map(context.session.delete, old_host_bindings)
        map(context.session.delete, old_interface_bindings)
