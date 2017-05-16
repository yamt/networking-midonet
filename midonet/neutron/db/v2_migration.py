
from oslo_utils import uuidutils

from neutron_lib import context as ctx

from neutron.db import api as db_api
from neutron.db import models_v2
from neutron.db import portbindings_db
from neutron.db import segments_db
from neutron.objects import network as network_obj
from neutron.plugins.ml2 import models as ml2_models

from midonet.neutron.db import provider_network_db
from midonet.neutron.db import port_binding_db


# midonet v2 port binding:
#    midonet_port_bindings (port_binding_db.PortBindingInfo)
#    portbindingports (portbindings_db.PortBindingPort)

# ml2 port binding:
#    ml2_port_bindings (ml2_models.PortBinding)
#    ml2_port_binding_levels (ml2_models.PortBindingLevel)
#    ml2_distributed_port_bindings (ml2_models.DistributedPortBinding)

# midonet v2 segments:
#    midonet_network_bindings (provider_network_db.NetworkBinding)

# ml2 segments:
#    networksegments (neutron.db.models.segment.NetworkSegment)


def add_segment(network_id, network_type):
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


def migrate():
    # Migrate db tables from v2 to ML2
    context = ctx.get_admin_context()
    with db_api.context_manager.writer.using(context):
        # TODO(yamamoto): locking
        # TODO(yamamoto): migrate port port binding
        # TODO(yamamoto): add a sanity check to ensure ml2 tables are empty
        # before migration
        old_segments = context.session.query(
            provider_network_db.NetworkBinding).all()
        uplink_network_ids = [seg.network_id for seg in old_segments]
        for network_id in uplink_network_ids:
            add_segment(network_id=network_id, network_type="uplink")
        networks = context.session.query(models_v2.Network).all()
        for net in networks:
            if net.id not in uplink_network_ids:
                add_segment(network_id=net.id, network_type="midonet")
        context.session.delete(old_segments)
