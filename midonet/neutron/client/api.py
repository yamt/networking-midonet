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

from midonet.neutron.client import base

from midonetclient import client


class MidonetApiClient(base.MidonetClientBase):

    def __init__(self, conf):
        self.api_cli = client.MidonetClient(conf.midonet_uri, conf.username,
                                            conf.password,
                                            project_id=conf.project_id)

    def create_network_postcommit(self, network):
        self.api_cli.create_network(network)

    def update_network_postcommit(self, network_id, network):
        self.api_cli.update_network(network_id, network)

    def delete_network_postcommit(self, network_id):
        self.api_cli.delete_network(network_id)

    def create_subnet_postcommit(self, subnet):
        self.api_cli.create_subnet(subnet)

    def update_subnet_postcommit(self, subnet_id, subnet):
        self.api_cli.update_subnet(subnet_id, subnet)

    def delete_subnet_postcommit(self, subnet_id):
        self.api_cli.delete_subnet(subnet_id)

    def create_port_postcommit(self, port):
        self.api_cli.create_port(port)

    def update_port_postcommit(self, port_id, port):
        self.api_cli.update_port(port_id, port)

    def delete_port_postcommit(self, port_id):
        self.api_cli.delete_port(port_id)

    def create_router_postcommit(self, router):
        self.api_cli.create_router(router)

    def update_router_postcommit(self, router_id, router):
        self.api_cli.update_router(router_id, router)

    def delete_router_postcommit(self, router_id):
        self.api_cli.delete_router(router_id)

    def add_router_interface_postcommit(self, router_id, interface_info):
        self.api_cli.add_router_interface(router_id, interface_info)

    def remove_router_interface_postcommit(self, router_id, interface_info):
        self.api_cli.remove_router_interface(router_id, interface_info)

    def create_floatingip_postcommit(self, floatingip):
        self.api_cli.create_floating_ip(floatingip)

    def update_floatingip_postcommit(self, floatingip_id, floatingip):
        self.api_cli.update_floating_ip(floatingip_id, floatingip)

    def delete_floatingip_postcommit(self, floatingip_id):
        self.api_cli.delete_floating_ip(floatingip_id)

    def create_security_group_postcommit(self, security_group):
        self.api_cli.create_security_group(security_group)

    def delete_security_group_postcommit(self, security_group_id):
        self.api_cli.delete_security_group(security_group_id)

    def create_security_group_rule_postcommit(self, security_group_rule):
        self.api_cli.create_security_group_rule(security_group_rule)

    def create_security_group_rule_bulk_postcommit(self, security_group_rules):
        self.api_cli.create_security_group_rule_bulk(security_group_rules)

    def delete_security_group_rule_postcommit(self, security_group_rule_id):
        self.api_cli.delete_security_group_rule(security_group_rule_id)

    def create_vip(self, context, vip):
        self.api_cli.create_vip(vip)

    def update_vip(self, context, vip_id, vip):
        self.api_cli.update_vip(vip_id, vip)

    def delete_vip(self, context, vip_id):
        self.api_cli.delete_vip(vip_id)

    def create_pool(self, context, pool):
        self.api_cli.create_pool(pool)

    def update_pool(self, context, pool_id, pool):
        self.api_cli.update_pool(pool_id, pool)

    def delete_pool(self, context, pool_id):
        self.api_cli.delete_pool(pool_id)

    def create_member(self, context, member):
        self.api_cli.create_member(member)

    def update_member(self, context, member_id, member):
        self.api_cli.update_member(member_id, member)

    def delete_member(self, context, member_id):
        self.api_cli.delete_member(member_id)

    def create_health_monitor(self, context, health_monitor):
        self.api_cli.create_health_monitor(health_monitor)

    def update_health_monitor(self, context, health_monitor_id,
                              health_monitor):
        self.api_cli.update_health_monitor(health_monitor_id, health_monitor)

    def delete_health_monitor(self, context, health_monitor_id):
        self.api_cli.delete_health_monitor(health_monitor_id)

    def create_firewall(self, context, firewall):
        self.api_cli.create_firewall(firewall)

    def delete_firewall(self, context, firewall):
        self.api_cli.delete_firewall(firewall['id'])

    def update_firewall(self, context, firewall):
        self.api_cli.update_firewall(firewall['id'], firewall)

    def create_vpn_service(self, context, vpn_service):
        self.api_cli.create_vpn_service(vpn_service)

    def update_vpn_service(self, context, vpn_service_id, vpn_service):
        self.api_cli.update_vpn_service(vpn_service_id, vpn_service)

    def delete_vpn_service(self, context, vpn_service_id):
        self.api_cli.delete_vpn_service(vpn_service_id)

    def create_ipsec_site_conn(self, context, ipsec_site_conn):
        self.api_cli.create_ipsec_site_conn(ipsec_site_conn)

    def update_ipsec_site_conn(self, context, ipsec_site_conn_id,
            ipsec_site_conn):
        self.api_cli.update_ipsec_site_conn(ipsec_site_conn_id,
                ipsec_site_conn)

    def delete_ipsec_site_conn(self, context, ipsec_site_conn_id):
        self.api_cli.delete_ipsec_site_conn(ipsec_site_conn_id)

    def create_gateway_device_postcommit(self, gw_dev):
        self.api_cli.create_gateway_device(gw_dev)

    def update_gateway_device_postcommit(self, gw_dev_id, gw_dev):
        self.api_cli.update_gateway_device(gw_dev_id, gw_dev)

    def delete_gateway_device_postcommit(self, gw_dev_id):
        self.api_cli.delete_gateway_device(gw_dev_id)

    def create_gateway_device_remote_mac_entry_postcommit(self, mac_entry):
        self.api_cli.create_remote_mac_entry(mac_entry)

    def delete_gateway_device_remote_mac_entry_postcommit(self, mac_entry_id):
        self.api_cli.delete_remote_mac_entry(mac_entry_id)

    def create_l2_gateway_connection(self, context, l2_gw_conn):
        self.api_cli.create_l2gw_conn(l2_gw_conn)

    def delete_l2_gateway_connection(self, context, l2_gw_conn_id):
        self.api_cli.delete_l2gw_conn(l2_gw_conn_id)

    # Tap as a service

    def create_tap_flow(self, context, tap_flow):
        self.api_cli.create_tap_flow(tap_flow)

    def update_tap_flow(self, context, tap_flow):
        self.api_cli.update_tap_flow(tap_flow)

    def delete_tap_flow(self, context, tap_flow_id):
        self.api_cli.delete_tap_flow(tap_flow_id)

    def create_tap_service(self, context, tap_service):
        self.api_cli.create_tap_service(tap_service)

    def update_tap_service(self, context, tap_service):
        self.api_cli.update_tap_service(tap_service)

    def delete_tap_service(self, context, tap_service_id):
        self.api_cli.delete_tap_service(tap_service_id)
