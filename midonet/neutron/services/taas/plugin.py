# Copyright (C) 2016 Midokura SARL
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg
from oslo_log import helpers as log_helpers

from neutron.api import extensions as neutron_extensions

from neutron_taas.services.taas import taas_plugin
from neutron_taas import extensions

from midonet.neutron.client import base as c_base


class MidonetTaasPlugin(taas_plugin.TaasPlugin):
    def __init__(self):
        self.client = c_base.load_client(cfg.CONF.MIDONET)
        # Register the extensions path
        neutron_extensions.append_api_extensions_path(extensions.__path__)
        super(MidonetTaasPlugin, self).__init__()

    @log_helpers.log_method_call
    def create_tap_flow(self, context, tap_flow):
        tf = super(MidonetTaasPlugin, self).create_tap_flow(context, tap_flow)
        self.client.create_tap_flow(context, tf)
        return tf

    @log_helpers.log_method_call
    def update_tap_flow(self, context, tap_flow):
        tf = super(MidonetTaasPlugin, self).update_tap_flow(context, tap_flow)
        self.client.delete_tap_flow(context, tf)
        return tf

    @log_helpers.log_method_call
    def delete_tap_flow(self, context, tap_flow_id):
        super(MidonetTaasPlugin, self).delete_tap_flow(context, tap_flow_id)
        self.client.delete_tap_flow(context, tap_flow_id)

    @log_helpers.log_method_call
    def create_tap_service(self, context, tap_service):
        ts = super(MidonetTaasPlugin, self).create_tap_service(context, tap_service)
        self.client.create_tap_service(context, ts)
        return ts

    @log_helpers.log_method_call
    def update_tap_service(self, context, tap_service):
        ts = super(MidonetTaasPlugin, self).update_tap_service(context, tap_service)
        self.client.delete_tap_service(context, ts)
        return ts

    @log_helpers.log_method_call
    def delete_tap_service(self, context, tap_service_id):
        super(MidonetTaasPlugin, self).delete_tap_service(context, tap_service_id)
        self.client.delete_tap_service(context, tap_service_id)
