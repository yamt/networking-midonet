# Copyright 2017 Midokura SARL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from os_vif import objects
from os_vif import plugin

from midonet.os_vif import linux_net
from midonet.os_vif import mm_ctl
from midonet.os_vif import privsep


class MidoNetPlugin(plugin.PluginBase):

    def describe(self):
        return objects.host_info.HostPluginInfo(
            plugin_name="midonet",
            vif_info=[
                objects.host_info.HostVIFInfo(
                    vif_object_name=objects.vif.VIFGeneric.__name__,
                    min_version="1.0",
                    max_version="1.0"),
            ])

    def plug(self, vif, instance_info):
        linux_net.create_tap_dev(vif.vif_name)
        _bind_port(vif.id, vif.vif_name)

    def unplug(self, vif, instance_info):
        _unbind_port(vif.id)
        linux_net.delete_net_dev(vif.vif_name)


@privsep.mm_ctl.entrypoint
def _bind_port(port_id, ifname):
    mm_ctl.bind_port(port_id, ifname)


@privsep.mm_ctl.entrypoint
def _unbind_port(port_id):
    mm_ctl.unbind_port(port_id)
