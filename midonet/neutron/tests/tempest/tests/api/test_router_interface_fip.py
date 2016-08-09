# Copyright (c) 2016 Midokura SARL
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

from tempest.lib.common.utils import data_utils
from tempest.lib import exceptions
from tempest import test

import testtools

from neutron.tests.tempest.api import base


class RouterInterfaceFip(base.BaseAdminNetworkTest):
    @classmethod
    @test.requires_ext(extension="router-interface-fip", service="network")
    def resource_setup(cls):
        super(RouterInterfaceFip, cls).resource_setup()

    @test.idempotent_id('943ab44d-0ea7-4c6a-bdfd-8ba759622992')
    def test_router_interface_fip(self):
        # +-------------+
        # | router1     |
        # +-+--------+--+
        #   |        |
        # +-+--+   +-+--------+
        # |net1|   |net2      |
        # |    |   |(external)|
        # +-+--+   +--+-------+
        #   |         |
        #  port1     fip2
        cidr1 = netaddr.IPNetwork('192.2.1.0/24')
        cidr2 = netaddr.IPNetwork('192.2.2.0/24')
        router1_name = data_utils.rand_name('router1')
        port1_name = data_utils.rand_name('port1')
        router1 = self.create_router(router1_name)
        net1 = self.create_network()
        subnet1 = self.create_subnet(net1, cidr=cidr1)
        ri1 = self.create_router_interface(router1['id'], subnet1['id'])
        net2 = self.admin_client.create_network(
            project_id=self.client.tenant_id,
            **{'router:external': True})['network']
        self.networks.append(net2)
        subnet2 = self.create_subnet(net2, cidr=cidr2)
        ri2 = self.create_router_interface(router1['id'], subnet2['id'])
        port1 = self.create_port(net1)
        fip2 = self.create_floatingip(net2['id'])
        self.client.update_floatingip(fip2['id'], port_id=port1['id'])
