# Copyright (C) 2017 Midokura SARL.
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

from neutron_lib.callbacks import events
from neutron_lib.callbacks import registry
from neutron_lib.callbacks import resources
from oslo_config import cfg
from oslo_log import helpers as log_helpers
from oslo_log import log as logging

from neutron.services.l3_router.service_providers import base

from midonet.neutron.client import base as c_base


LOG = logging.getLogger(__name__)


# service_plugins = ...,router,...
#
# [service_providers]
# service_provider = L3_ROUTER_NAT:Midonet:midonet.neutron.services.l3.service_providers.l3_midonet.MidoNetL3ServiceProvider:default



# openstack network flavor profile create --driver midonet.neutron.services.l3.service_providers.l3_midonet.MidoNetL3ServiceProvider
# openstack network flavor create --service-type L3_ROUTER_NAT midonet
# openstack network flavor add profile midonet ${profile}
# neutron router-create --flavor midonet hoge


# TODO(yamamoto): precommit events for task-based api
# It isn't straightforward because the reference L3 service plugin itself
# (driver_controller) uses a few precommit events to update resource
# associations and the callback framework has no notion of the order of
# receivers.
# TODO(yamamoto): ignore router requests if it isn't associated to this driver
# TODO(yamamoto): ignore floating-ip on non-midonet networks
# TODO(yamamoto): reject router interface on non-midonet networks
# TODO(yamamoto): reject gateway port on non-midonet networks
# TODO(yamamoto): fip64 extension
# TODO(yamamoto): router-interface-fip extension
# TODO(yamamoto): error handling
# TODO(yamamoto): documentation
# TODO(yamamoto): devstack support
@registry.has_registry_receivers
class MidoNetL3ServiceProvider(base.L3ServiceProvider):
    @log_helpers.log_method_call
    def __init__(self, l3_plugin):
        super(MidoNetL3ServiceProvider, self).__init__(l3_plugin)
        self.client = c_base.load_client(cfg.CONF.MIDONET)
        self.client.initialize()

    @registry.receives(resources.ROUTER, [events.AFTER_CREATE])
    @log_helpers.log_method_call
    def _router_after_create(self, resource, event, trigger, **kwargs):
        router = kwargs['router']
        self.client.create_router_postcommit(router)

    @registry.receives(resources.ROUTER, [events.AFTER_UPDATE])
    @log_helpers.log_method_call
    def _router_after_update(self, resource, event, trigger, **kwargs):
        router = kwargs['router']
        self.client.update_router_postcommit(router)

    @registry.receives(resources.ROUTER, [events.AFTER_DELETE])
    @log_helpers.log_method_call
    def _router_after_delete(self, resource, event, trigger, **kwargs):
        router_id = kwargs['router_id']
        self.client.delete_router_postcommit(router_id)

    @registry.receives(resources.ROUTER_INTERFACE, [events.AFTER_CREATE])
    @log_helpers.log_method_call
    def _add_router_interface(self, resource, event, trigger, **kwargs):
        info = kwargs['router_interface_info']
        router_id = info['id']
        self.client.add_router_interface_postcommit(router_id, info)

    @registry.receives(resources.ROUTER_INTERFACE, [events.AFTER_DELETE])
    @log_helpers.log_method_call
    def _remove_router_interface(self, resource, event, trigger, **kwargs):
        info = kwargs['router_interface_info']
        router_id = info['id']
        self.client.remove_router_interface_postcommit(router_id, info)

    @registry.receives(resources.FLOATING_IP, [events.AFTER_CREATE])
    @log_helpers.log_method_call
    def _create_floatingip(self, resource, event, trigger, **kwargs):
        fip = kwargs['floating_ip']
        self.client.create_floatingip_postcommit(fip)

    @registry.receives(resources.FLOATING_IP, [events.AFTER_UPDATE])
    @log_helpers.log_method_call
    def _update_floatingip(self, resource, event, trigger, **kwargs):
        fip = kwargs.get('floating_ip', None)
        if fip is None:
            return
        self.client.update_floatingip_postcommit(fip)

    @registry.receives(resources.FLOATING_IP, [events.AFTER_DELETE])
    @log_helpers.log_method_call
    def _delete_floatingip(self, resource, event, trigger, **kwargs):
        id = kwargs['id']
        self.client.delete_floatingip_postcommit(id)
