# Copyright (C) 2015 Midokura SARL.
# All Rights Reserved.
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

import netaddr
from sqlalchemy import orm

from midonet.neutron._i18n import _LE, _LW
from midonet.neutron.client import base as c_base
from midonet.neutron.common import config  # noqa
from midonet.neutron.common import constants as m_const
from midonet.neutron.db import l3_db_midonet
from midonet.neutron import extensions
from midonet.neutron.extensions import routerinterfacefip

from neutron.api import extensions as neutron_extensions
from neutron.callbacks import events
from neutron.callbacks import exceptions
from neutron.callbacks import registry
from neutron.callbacks import resources
from neutron.common import constants as n_const
from neutron.common import exceptions as n_exc
from neutron.db import common_db_mixin
from neutron.db import extraroute_db
from neutron.db import l3_db
# Import l3_dvr_db to get the config options required for FWaaS
from neutron.db import l3_dvr_db  # noqa
from neutron.db import models_v2
from neutron.extensions import l3
from neutron.extensions import multiprovidernet as mpnet
from neutron.extensions import providernet as pnet
from neutron.plugins.common import constants
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging
from oslo_utils import excutils

LOG = logging.getLogger(__name__)


class MidonetL3ServicePlugin(common_db_mixin.CommonDbMixin,
                             extraroute_db.ExtraRoute_db_mixin,
                             l3_db_midonet.MidonetL3DBMixin):

    """
    Implements L3 Router service plugin for Midonet.
    """

    supported_extension_aliases = ["router", "extraroute", "ext-gw-mode",
                                   "router-interface-fip"]

    def __init__(self):
        super(MidonetL3ServicePlugin, self).__init__()
        l3_db.subscribe()
        self.__subscribe()

        # Instantiate MidoNet API client
        self.client = c_base.load_client(cfg.CONF.MIDONET)

        # Avoid any side effect from DVR getting set to true
        cfg.CONF.set_override("router_distributed", False)
        neutron_extensions.append_api_extensions_path(extensions.__path__)

    def get_plugin_type(self):
        return constants.L3_ROUTER_NAT

    def get_plugin_description(self):
        """Returns string description of the plugin."""
        return ("Midonet L3 Router Service Plugin")

    @staticmethod
    def _segments(network):
        if pnet.NETWORK_TYPE in network:
            yield {
                pnet.NETWORK_TYPE: network[pnet.NETWORK_TYPE],
            }
        segments = network.get(mpnet.SEGMENTS)
        if segments:
            for seg in segments:
                yield seg

    def _validate_network_type(self, context, network_id):
        our_types = [m_const.TYPE_MIDONET, m_const.TYPE_UPLINK]
        network = self._core_plugin.get_network(context, network_id)
        for seg in self._segments(network):
            if seg[pnet.NETWORK_TYPE] in our_types:
                return
        LOG.warning(_LW("Incompatible network %s"), network)
        raise n_exc.BadRequest(resource='router', msg='Incompatible network')

    def _validate_router_gw_network(self, context, r):
        ext_gw_info = r.get(l3.EXTERNAL_GW_INFO)
        if ext_gw_info:
            self._validate_network_type(context, ext_gw_info['network_id'])

    @log_helpers.log_method_call
    def create_router(self, context, router):
        with context.session.begin(subtransactions=True):
            r = super(MidonetL3ServicePlugin, self).create_router(context,
                                                                  router)
            self._validate_router_gw_network(context, r)
            self.client.create_router_precommit(context, r)

        try:
            self.client.create_router_postcommit(r)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create a router %(r_id)s in Midonet:"
                              "%(err)s"), {"r_id": r["id"], "err": ex})
                try:
                    self.delete_router(context, r['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete a router %s"), r["id"])
        return r

    @log_helpers.log_method_call
    def update_router(self, context, id, router):
        with context.session.begin(subtransactions=True):
            r = super(MidonetL3ServicePlugin, self).update_router(context, id,
                                                                  router)
            self._validate_router_gw_network(context, r)
            self.client.update_router_precommit(context, id, r)

        try:
            self.client.update_router_postcommit(id, r)
            if r['status'] != m_const.ROUTER_STATUS_ACTIVE:
                data = {'router': {'status': m_const.ROUTER_STATUS_ACTIVE}}
                r = super(MidonetL3ServicePlugin,
                        self).update_router(context, id, data)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to update a router %(r_id)s in MidoNet: "
                              "%(err)s"), {"r_id": id, "err": ex})
                try:
                    data = {'router': {'status': m_const.ROUTER_STATUS_ERROR}}
                    super(MidonetL3ServicePlugin,
                        self).update_router(context, id, data)
                except Exception:
                    LOG.exception(_LE("Failed to update a router "
                                      "status %s"), id)
        return r

    @log_helpers.log_method_call
    def delete_router(self, context, id):
        self._check_router_not_in_use(context, id)

        with context.session.begin(subtransactions=True):
            super(MidonetL3ServicePlugin, self).delete_router(context, id)
            self.client.delete_router_precommit(context, id)

        self.client.delete_router_postcommit(id)

    @log_helpers.log_method_call
    def add_router_interface(self, context, router_id, interface_info):
        by_port = bool(interface_info.get('port_id'))
        with context.session.begin(subtransactions=True):
            info = super(MidonetL3ServicePlugin, self).add_router_interface(
                context, router_id, interface_info)
            self._validate_network_type(context, info['network_id'])
            self.client.add_router_interface_precommit(context, router_id,
                                                       info)

        try:
            self.client.add_router_interface_postcommit(router_id, info)
        except Exception as ex:
            LOG.error(_LE("Failed to create MidoNet resources to add router "
                          "interface. info=%(info)s, router_id=%(router_id)s, "
                          "error=%(err)r"),
                      {"info": info, "router_id": router_id, "err": ex})
            with excutils.save_and_reraise_exception():
                if not by_port:
                    self.remove_router_interface(context, router_id, info)

        return info

    @log_helpers.log_method_call
    def remove_router_interface(self, context, router_id, interface_info):
        with context.session.begin(subtransactions=True):
            info = super(MidonetL3ServicePlugin, self).remove_router_interface(
                context, router_id, interface_info)
            self.client.remove_router_interface_precommit(context, router_id,
                                                          info)

        self.client.remove_router_interface_postcommit(router_id, info)
        return info

    @log_helpers.log_method_call
    def create_floatingip(self, context, floatingip):
        with context.session.begin(subtransactions=True):
            fip = super(MidonetL3ServicePlugin, self).create_floatingip(
                context, floatingip)
            self.client.create_floatingip_precommit(context, fip)

        try:
            self.client.create_floatingip_postcommit(fip)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create floating ip %(fip)s: %(err)s"),
                          {"fip": fip, "err": ex})
                try:
                    self.delete_floatingip(context, fip['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete a floating ip %s"),
                                  fip['id'])
        return fip

    @log_helpers.log_method_call
    def delete_floatingip(self, context, id):
        with context.session.begin(subtransactions=True):
            super(MidonetL3ServicePlugin, self).delete_floatingip(context, id)
            self.client.delete_floatingip_precommit(context, id)

        self.client.delete_floatingip_postcommit(id)

    @log_helpers.log_method_call
    def update_floatingip(self, context, id, floatingip):
        with context.session.begin(subtransactions=True):
            fip = super(MidonetL3ServicePlugin, self).update_floatingip(
                context, id, floatingip)
            port_id = fip['port_id']
            if port_id is not None:
                port = self._core_plugin.get_port(context, port_id)
                owner = port['device_owner']
                # REVISIT(yamamoto): Empty owner is allowed for tempest and
                # unit tests.
                # NOTE(yamamoto): VIP is allowed for non MidoNet LB providers
                if (owner and
                   not owner.startswith(n_const.DEVICE_OWNER_COMPUTE_PREFIX)
                   and owner != n_const.DEVICE_OWNER_LOADBALANCER):
                    raise n_exc.UnsupportedPortDeviceOwner(
                        op='floatingip association',
                        port_id=port_id,
                        device_owner=owner)

            self.client.update_floatingip_precommit(context, id, fip)

            # Update status based on association
            if fip.get('port_id') is None:
                fip['status'] = n_const.FLOATINGIP_STATUS_DOWN
            else:
                fip['status'] = n_const.FLOATINGIP_STATUS_ACTIVE
            self.update_floatingip_status(context, id, fip['status'])

        try:
            self.client.update_floatingip_postcommit(id, fip)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to update a floating ip "
                              "%(fip_id)s in MidoNet: "
                              "%(err)s"), {"fip_id": id, "err": ex})
                try:
                    self.update_floatingip_status(
                            context, id, n_const.FLOATINGIP_STATUS_ERROR)
                except Exception:
                    LOG.exception(_LE("Failed to update floating ip "
                                      "status %s"), id)
        return fip

    def get_router_for_floatingip(self, context, internal_port,
            internal_subnet, external_network_id):
        # REVISIT(yamamoto): These direct manipulation of core-plugin db
        # resources is not ideal.
        gw_port = orm.aliased(models_v2.Port, name="gw_port")
        routerport_qry = context.session.query(
            l3_db.RouterPort.router_id,
            models_v2.IPAllocation.ip_address
        ).join(
            models_v2.Port, models_v2.IPAllocation
        ).filter(
            models_v2.Port.network_id == internal_port['network_id'],
            l3_db.RouterPort.port_type.in_(
                n_const.ROUTER_INTERFACE_OWNERS
            ),
            models_v2.IPAllocation.subnet_id == internal_subnet['id']
        ).join(
            gw_port, gw_port.device_id == l3_db.RouterPort.router_id
        ).filter(
            gw_port.network_id == external_network_id,
        ).distinct()

        first_router_id = None
        for router_id, interface_ip in routerport_qry:
            if interface_ip == internal_subnet['gateway_ip']:
                return router_id
            if not first_router_id:
                first_router_id = router_id
        if first_router_id:
            return first_router_id

        raise l3.ExternalGatewayForFloatingIPNotFound(
            subnet_id=internal_subnet['id'],
            external_network_id=external_network_id,
            port_id=internal_port['id'])

    def _subnet_has_fip(self, context, router_id, subnet_id):
        # Return True if the subnet has one of floating IPs for the router
        subnet = self._core_plugin.get_subnet(context, subnet_id)
        subnet_cidr = netaddr.IPNetwork(subnet['cidr'])
        fip_qry = context.session.query(l3_db.FloatingIP)
        fip_qry = fip_qry.filter_by(router_id=router_id)
        for fip_db in fip_qry:
            if netaddr.IPAddress(fip_db['floating_ip_address']) in subnet_cidr:
                return True
        return False

    # REVISIT(yamamoto): This method is a copy of the base class method,
    # with modified RouterExternalGatewayInUseByFloatingIp validation.
    def _delete_current_gw_port(self, context, router_id, router,
                                new_network_id):
        """Delete gw port if attached to an old network."""
        port_requires_deletion = (
            router.gw_port and router.gw_port['network_id'] != new_network_id)
        if not port_requires_deletion:
            return
        admin_ctx = context.elevated()
        old_network_id = router.gw_port['network_id']

        for ip in router.gw_port['fixed_ips']:
            if self._subnet_has_fip(admin_ctx, router_id, ip['subnet_id']):
                raise l3.RouterExternalGatewayInUseByFloatingIp(
                    router_id=router_id, net_id=router.gw_port['network_id'])
        gw_ips = [x['ip_address'] for x in router.gw_port.fixed_ips]
        with context.session.begin(subtransactions=True):
            gw_port = router.gw_port
            router.gw_port = None
            context.session.add(router)
            context.session.expire(gw_port)
            self._check_router_gw_port_in_use(context, router_id)
        self._core_plugin.delete_port(
            admin_ctx, gw_port['id'], l3_port_check=False)
        registry.notify(resources.ROUTER_GATEWAY,
                        events.AFTER_DELETE, self,
                        router_id=router_id,
                        network_id=old_network_id,
                        gateway_ips=gw_ips)

    # REVISIT(yamamoto): This method is a copy of the base class method,
    # with 'router_id' notification argument added.
    def _confirm_router_interface_not_in_use(self, context, router_id,
                                             subnet_id):
        subnet = self._core_plugin.get_subnet(context, subnet_id)
        subnet_cidr = netaddr.IPNetwork(subnet['cidr'])
        fip_qry = context.session.query(l3_db.FloatingIP)
        try:
            kwargs = {'context': context, 'subnet_id': subnet_id,
                      'router_id': router_id}
            registry.notify(
                resources.ROUTER_INTERFACE,
                events.BEFORE_DELETE, self, **kwargs)
        except exceptions.CallbackFailure as e:
            with excutils.save_and_reraise_exception():
                # NOTE(armax): preserve old check's behavior
                if len(e.errors) == 1:
                    raise e.errors[0].error
                raise l3.RouterInUse(router_id=router_id, reason=e)
        for fip_db in fip_qry.filter_by(router_id=router_id):
            if netaddr.IPAddress(fip_db['fixed_ip_address']) in subnet_cidr:
                raise l3.RouterInterfaceInUseByFloatingIP(
                    router_id=router_id, subnet_id=subnet_id)

    def _check_router_interface_used_as_gw_for_fip(self, resource,
                                                   event, trigger, **kwargs):
        context = kwargs['context']
        router_id = kwargs['router_id']
        subnet_id = kwargs['subnet_id']
        if self._subnet_has_fip(context, router_id, subnet_id):
            raise routerinterfacefip.RouterInterfaceInUseAsGatewayByFloatingIP(
                router_id=router_id, subnet_id=subnet_id)

    def __subscribe(self):
        registry.subscribe(
            self._check_router_interface_used_as_gw_for_fip,
            resources.ROUTER_INTERFACE,
            events.BEFORE_DELETE)
