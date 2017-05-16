

from oslo_log import log as logging
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


def add_binding_bound(context, port_id, segment_id, host, interface_name):
    context.session.add(ml2_models.PortBindingLevel(
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
        profile=profile,
        vif_details={'port_filter': True},
        status='ACTIVE'))


def add_binding_unbound(context, port_id):
    # ml2 add_port_binding equiv
    context.session.add(ml2_models.PortBinding(
        port_id=port_id,
        vif_type='unbound',
        vnic_type='normal',
        profile='',
        vif_details='',
        status='ACTIVE'))


def migrate():
    # Migrate db tables from v2 to ML2
    context = ctx.get_admin_context()
    with db_api.context_manager.writer.using(context):
        # TODO(yamamoto): locking

        # Migrate network segments
        segments = {}
        old_segments = context.session.query(
            provider_network_db.NetworkBinding).all()
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
        old_host_bindings = context.session.query(
            portbinding.PortBindingPort).all()
        old_interface_bindings = context.session.query(
            port_binding_db.PortBindingInfo).all()
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
        context.session.delete(provider_network_db.NetworkBinding)
        context.session.delete(portbinding.PortBindingPort)
        context.session.delete(port_binding_db.PortBindingInfo)

        raise Exception("rollback")
