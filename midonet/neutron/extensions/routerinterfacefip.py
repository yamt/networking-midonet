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

from neutron.api import extensions
from neutron.common import exceptions as n_exc

from midonet.neutron._i18n import _


class RouterInterfaceInUseAsGatewayByFloatingIP(n_exc.InUse):
    message = _("Router interface for subnet %(subnet_id)s on router "
                "%(router_id)s cannot be deleted, as it is required "
                "by one or more floating IPs as a gateway.")


class Routerinterfacefip(extensions.ExtensionDescriptor):
    """Router interface FIP extension."""

    @classmethod
    def get_name(cls):
        return "MidoNet Router interface FIP Extension"

    @classmethod
    def get_alias(cls):
        return "router-interface-fip"

    @classmethod
    def get_description(cls):
        return "MidoNet Router interface FIP Extension"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/router-interface-fip/api/v2.0"

    @classmethod
    def get_updated(cls):
        return "2015-11-11T10:00:00-00:00"
