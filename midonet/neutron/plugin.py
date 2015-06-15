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

from midonet.neutron.common import config  # noqa
from midonet.neutron.db import agent_membership_db as am_db
from midonet.neutron.db import port_binding_db as pb_db
from midonet.neutron.db import provider_network_db as pnet_db
from midonet.neutron import extensions
from neutron.api import extensions as neutron_extensions
from neutron.api.rpc.handlers import dhcp_rpc
from neutron.api.rpc.handlers import metadata_rpc
from neutron.common import constants as n_const
from neutron.common import exceptions as n_exc
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.db import agents_db
from neutron.db import agentschedulers_db
from neutron.db import allowedaddresspairs_db as addr_pair_db
from neutron.db import db_base_plugin_v2
from neutron.db import external_net_db
from neutron.db import extradhcpopt_db
from neutron.db import extraroute_db
from neutron.db import l3_gwmode_db
from neutron.db import portbindings_db
from neutron.db import securitygroups_db
from neutron.extensions import allowedaddresspairs as addr_pair
from neutron.extensions import extra_dhcp_opt as edo_ext
from neutron.extensions import portbindings
from neutron.extensions import providernet as pnet
from neutron.extensions import securitygroup as ext_sg
from neutron import i18n
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import importutils


LOG = logging.getLogger(__name__)
_LE = i18n._LE
_SUPPORTED_EXTENSIONS = ['extra_dhcp_opt']
_VALID_EXTRA_EXTENSIONS = {'allowed-address-pairs', 'agent-membership',
                           'extraroute', 'provider'}


def _verify_extra_extensions_valid(extra_extensions):
    """Verifies that the extra extensions provided are legitimate.

    This method expects a set, not a list.  TypeError will be thrown if
    anything other than a set is provided, including None.
    """
    invalid_extensions = extra_extensions - _VALID_EXTRA_EXTENSIONS
    if invalid_extensions:
        msg = _LE("Invalid extra extensions detected: "
                  "%(ext)s") % {'ext': invalid_extensions}
        LOG.error(msg)
        raise SystemExit(1)


class MidonetMixin(addr_pair_db.AllowedAddressPairsMixin,
                   agentschedulers_db.DhcpAgentSchedulerDbMixin,
                   am_db.AgentMembershipDbMixin,
                   db_base_plugin_v2.NeutronDbPluginV2,
                   external_net_db.External_net_db_mixin,
                   extradhcpopt_db.ExtraDhcpOptMixin,
                   extraroute_db.ExtraRoute_db_mixin,
                   l3_gwmode_db.L3_NAT_db_mixin,
                   pnet_db.MidonetProviderNetworkMixin,
                   pb_db.MidonetPortBindingMixin,
                   portbindings_db.PortBindingMixin,
                   securitygroups_db.SecurityGroupDbMixin):

    # The extensions are now loaded in __init__, so this variable is not
    # required.  However it must remain here because the parent plugin accesses
    # it when constructing the supported extension list.
    # TODO(ryu): Change MidonetPluginV2 to not access this variable so that
    # it can be removed
    supported_extension_aliases = []

    def __init__(self):
        super(MidonetMixin, self).__init__()

        # Load the supported extensions
        extra_extensions = set(cfg.CONF.MIDONET.extra_extensions)
        _verify_extra_extensions_valid(extra_extensions)
        all_exts = (self.supported_extension_aliases + _SUPPORTED_EXTENSIONS +
                    list(extra_extensions))
        self.supported_extension_aliases = list(set(all_exts))

        neutron_extensions.append_api_extensions_path(extensions.__path__)
        self.setup_rpc()

        # Instantiate MidoNet client and initialize
        self._load_client()
        self.client.initialize()

        self.base_binding_dict = {
            portbindings.VIF_TYPE: portbindings.VIF_TYPE_MIDONET,
            portbindings.VNIC_TYPE: portbindings.VNIC_NORMAL,
            portbindings.VIF_DETAILS: {
                # TODO(rkukura): Replace with new VIF security details
                portbindings.CAP_PORT_FILTER:
                'security-group' in self.supported_extension_aliases}}
        self.network_scheduler = importutils.import_object(
            cfg.CONF.network_scheduler_driver
        )

    def _load_client(self):
        try:
            self.client = importutils.import_object(cfg.CONF.MIDONET.client)
            LOG.debug("Loaded midonet client '%(client)s'",
                      {'client': self.client})
        except ImportError:
            with excutils.save_and_reraise_exception():
                LOG.exception(_LE("Error loading midonet client '%(client)s'"),
                              {'client': self.client})

    def setup_rpc(self):
        # RPC support
        self.topic = topics.PLUGIN
        self.conn = n_rpc.create_connection(new=True)
        self.endpoints = [dhcp_rpc.DhcpRpcCallback(),
                          agents_db.AgentExtRpcCallback(),
                          metadata_rpc.MetadataRpcCallback()]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        # Consume from all consumers in a thread
        self.conn.consume_in_threads()

    def create_network(self, context, network):
        LOG.debug('MidonetMixin.create_network called: network=%r', network)

        net_data = network['network']
        tenant_id = self._get_tenant_id_for_create(context, net_data)
        net_data['tenant_id'] = tenant_id
        self._ensure_default_security_group(context, tenant_id)

        with context.session.begin(subtransactions=True):
            net = super(MidonetMixin, self).create_network(context, network)
            net_data['id'] = net['id']
            self._process_l3_create(context, net, net_data)
            self._create_provider_network(context, net_data)
            self._extend_provider_network_dict(context, net)
            self.client.create_network_precommit(context, net)

        try:
            self.client.create_network_postcommit(net)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create a network %(net_id)s "
                              "in Midonet: %(err)s"),
                          {"net_id": net["id"], "err": ex})
                try:
                    self.delete_network(context, net['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete network %s"),
                                  net['id'])

        LOG.debug("MidonetMixin.create_network exiting: net=%r", net)
        return net

    def get_network(self, context, id, fields=None):
        LOG.debug("MidonetMixin.get_network called: id=%(id)r", {'id': id})

        session = context.session
        with session.begin(subtransactions=True):
            net = super(MidonetMixin, self).get_network(context, id, None)
            self._extend_provider_network_dict(context, net)

        return self._fields(net, fields)

    def get_networks(self, context, filters=None, fields=None,
                     sorts=None, limit=None, marker=None, page_reverse=False):
        LOG.debug("MidonetMixin.get_networks called: filters=%(filters)r",
                  {'filters': filters})

        session = context.session
        with session.begin(subtransactions=True):
            nets = super(MidonetMixin,
                         self).get_networks(context, filters, None, sorts,
                                            limit, marker, page_reverse)
            for net in nets:
                self._extend_provider_network_dict(context, net)

            nets = self._filter_nets_provider(nets, filters)

        return [self._fields(net, fields) for net in nets]

    def update_network(self, context, id, network):
        LOG.debug("MidonetMixin.update_network called: id=%(id)r, "
                  "network=%(network)r", {'id': id, 'network': network})

        # Disallow update of provider net
        net_data = network['network']
        pnet._raise_if_updates_provider_attributes(net_data)

        with context.session.begin(subtransactions=True):
            net = super(MidonetMixin, self).update_network(
                context, id, network)
            self._process_l3_update(context, net, network['network'])
            self._extend_provider_network_dict(context, net)
            self.client.update_network_precommit(context, id, net)

        self.client.update_network_postcommit(id, net)

        LOG.debug("MidonetMixin.update_network exiting: net=%r", net)
        return net

    def delete_network(self, context, id):
        LOG.debug("MidonetMixin.delete_network called: id=%r", id)

        with context.session.begin(subtransactions=True):
            self._process_l3_delete(context, id)
            super(MidonetMixin, self).delete_network(context, id)
            self.client.delete_network_precommit(context, id)

        self.client.delete_network_postcommit(id)

        LOG.debug("MidonetMixin.delete_network exiting: id=%r", id)

    def create_subnet(self, context, subnet):
        LOG.debug("MidonetMixin.create_subnet called: subnet=%r", subnet)

        with context.session.begin(subtransactions=True):
            s = super(MidonetMixin, self).create_subnet(context, subnet)
            self.client.create_subnet_precommit(context, s)

        try:
            self.client.create_subnet_postcommit(s)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create a subnet %(s_id)s in Midonet:"
                              "%(err)s"), {"s_id": s["id"], "err": ex})
                try:
                    self.delete_subnet(context, s['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete subnet %s"), s['id'])

        LOG.debug("MidonetMixin.create_subnet exiting: subnet=%r", s)
        return s

    def delete_subnet(self, context, id):
        LOG.debug("MidonetMixin.delete_subnet called: id=%s", id)

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).delete_subnet(context, id)
            self.client.delete_subnet_precommit(context, id)

        self.client.delete_subnet_postcommit(id)

        LOG.debug("MidonetMixin.delete_subnet exiting")

    def update_subnet(self, context, id, subnet):
        LOG.debug("MidonetMixin.update_subnet called: id=%s", id)

        with context.session.begin(subtransactions=True):
            s = super(MidonetMixin, self).update_subnet(context, id, subnet)
            self.client.update_subnet_precommit(context, id, s)

        self.client.update_subnet_postcommit(id, s)

        LOG.debug("MidonetMixin.update_subnet exiting: subnet=%r", s)
        return s

    def create_port(self, context, port):
        LOG.debug("MidonetMixin.create_port called: port=%r", port)

        port_data = port['port']
        with context.session.begin(subtransactions=True):
            # Create a Neutron port
            new_port = super(MidonetMixin, self).create_port(context, port)
            dhcp_opts = port['port'].get(edo_ext.EXTRADHCPOPTS, [])

            # Make sure that the port created is valid
            if "id" not in new_port:
                raise n_exc.BadRequest(resource='port',
                                       msg="Invalid port created")

            # Update fields
            port_data.update(new_port)

            # Bind security groups to the port
            self._ensure_default_security_group_on_port(context, port)
            sg_ids = self._get_security_groups_on_port(context, port)
            self._process_port_create_security_group(context, new_port, sg_ids)

            # Process port bindings
            self._process_portbindings_create_and_update(context, port_data,
                                                         new_port)
            self._process_mido_portbindings_create_and_update(context,
                                                              port_data,
                                                              new_port)

            self._process_port_create_extra_dhcp_opts(context, new_port,
                                                      dhcp_opts)

            new_port[addr_pair.ADDRESS_PAIRS] = (
                self._process_create_allowed_address_pairs(
                    context, new_port,
                    port_data.get(addr_pair.ADDRESS_PAIRS)))

            self.client.create_port_precommit(context, new_port)

        try:
            self.client.create_port_postcommit(new_port)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create a port %(new_port)s: %(err)s"),
                          {"new_port": new_port, "err": ex})
                try:
                    self.delete_port(context, new_port['id'],
                                     l3_port_check=False)
                except Exception:
                    LOG.exception(_LE("Failed to delete port %s"),
                                  new_port['id'])

        LOG.debug("MidonetMixin.create_port exiting: port=%r", new_port)
        return new_port

    def delete_port(self, context, id, l3_port_check=True):
        LOG.debug("MidonetMixin.delete_port called: id=%(id)s "
                  "l3_port_check=%(l3_port_check)r",
                  {'id': id, 'l3_port_check': l3_port_check})

        # if needed, check to see if this is a port owned by
        # and l3-router.  If so, we should prevent deletion.
        if l3_port_check:
            self.prevent_l3_port_deletion(context, id)

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).disassociate_floatingips(
                context, id, do_notify=False)
            super(MidonetMixin, self).delete_port(context, id)
            self.client.delete_port_precommit(context, id)

        self.client.delete_port_postcommit(id)

        LOG.debug("MidonetMixin.delete_port exiting: id=%r", id)

    def update_port(self, context, id, port):
        LOG.debug("MidonetMixin.update_port called: id=%(id)s port=%(port)r",
                  {'id': id, 'port': port})

        with context.session.begin(subtransactions=True):

            # update the port DB
            original_port = super(MidonetMixin, self).get_port(context, id)
            p = super(MidonetMixin, self).update_port(context, id, port)

            has_sg = self._check_update_has_security_groups(port)
            delete_sg = self._check_update_deletes_security_groups(port)

            if delete_sg or has_sg:
                # delete the port binding and read it with the new rules.
                self._delete_port_security_group_bindings(context, id)
                sg_ids = self._get_security_groups_on_port(context, port)
                self._process_port_create_security_group(context, p, sg_ids)
            self._update_extra_dhcp_opts_on_port(context, id, port, p)

            self._process_portbindings_create_and_update(context,
                                                         port['port'], p)
            self._process_mido_portbindings_create_and_update(context,
                                                              port['port'], p)
            self.update_address_pairs_on_port(context, id, port,
                                              original_port, p)

            self.client.update_port_precommit(context, id, p)

        self.client.update_port_postcommit(id, p)

        LOG.debug("MidonetMixin.update_port exiting: p=%r", p)
        return p

    def create_router(self, context, router):
        LOG.debug("MidonetMixin.create_router called: router=%(router)s",
                  {"router": router})

        with context.session.begin(subtransactions=True):
            r = super(MidonetMixin, self).create_router(context, router)
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

        LOG.debug("MidonetMixin.create_router exiting: router=%(router)s.",
                  {"router": r})
        return r

    def update_router(self, context, id, router):
        LOG.debug("MidonetMixin.update_router called: id=%(id)s "
                  "router=%(router)r", {"id": id, "router": router})

        with context.session.begin(subtransactions=True):
            r = super(MidonetMixin, self).update_router(context, id, router)
            self.client.update_router_precommit(context, id, r)

        self.client.update_router_postcommit(id, r)

        LOG.debug("MidonetMixin.update_router exiting: router=%r", r)
        return r

    def delete_router(self, context, id):
        LOG.debug("MidonetMixin.delete_router called: id=%s", id)

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).delete_router(context, id)
            self.client.delete_router_precommit(context, id)

        self.client.delete_router_postcommit(id)

        LOG.debug("MidonetMixin.delete_router exiting: id=%s", id)

    def add_router_interface(self, context, router_id, interface_info):
        LOG.debug("MidonetMixin.add_router_interface called: "
                  "router_id=%(router_id)s, interface_info=%(interface_info)r",
                  {'router_id': router_id, 'interface_info': interface_info})

        with context.session.begin(subtransactions=True):
            info = super(MidonetMixin, self).add_router_interface(
                context, router_id, interface_info)
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
                self.remove_router_interface(context, router_id, info)

        LOG.debug("MidonetMixin.add_router_interface exiting: info=%r", info)
        return info

    def remove_router_interface(self, context, router_id, interface_info):
        LOG.debug("MidonetMixin.remove_router_interface called: "
                  "router_id=%(router_id)s, interface_info=%(interface_info)r",
                  {'router_id': router_id, 'interface_info': interface_info})

        with context.session.begin(subtransactions=True):
            info = super(MidonetMixin, self).remove_router_interface(
                context, router_id, interface_info)
            self.client.remove_router_interface_precommit(context, router_id,
                                                          info)

        self.client.remove_router_interface_postcommit(router_id, info)

        LOG.debug("MidonetMixin.remove_router_interface exiting: info=%r",
                  info)
        return info

    def create_floatingip(self, context, floatingip):
        LOG.debug("MidonetMixin.create_floatingip called: ip=%r", floatingip)

        with context.session.begin(subtransactions=True):
            fip = super(MidonetMixin, self).create_floatingip(context,
                                                              floatingip)
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

        LOG.debug("MidonetMixin.create_floatingip exiting: fip=%r", fip)
        return fip

    def delete_floatingip(self, context, id):
        LOG.debug("MidonetMixin.delete_floatingip called: id=%s", id)

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).delete_floatingip(context, id)
            self.client.delete_floatingip_precommit(context, id)

        self.client.delete_floatingip_postcommit(id)

        LOG.debug("MidonetMixin.delete_floatingip exiting: id=%r", id)

    def update_floatingip(self, context, id, floatingip):
        LOG.debug("MidonetMixin.update_floatingip called: id=%(id)s "
                  "floatingip=%(floatingip)s ",
                  {'id': id, 'floatingip': floatingip})

        with context.session.begin(subtransactions=True):
            fip = super(MidonetMixin, self).update_floatingip(context, id,
                                                              floatingip)
            self.client.update_floatingip_precommit(context, id, fip)

            # Update status based on association
            if fip.get('port_id') is None:
                fip['status'] = n_const.FLOATINGIP_STATUS_DOWN
            else:
                fip['status'] = n_const.FLOATINGIP_STATUS_ACTIVE
            self.update_floatingip_status(context, id, fip['status'])

        self.client.update_floatingip_postcommit(id, fip)

        LOG.debug("MidonetMixin.update_floating_ip exiting: fip=%s", fip)
        return fip

    def create_security_group(self, context, security_group, default_sg=False):
        LOG.debug("MidonetMixin.create_security_group called: "
                  "security_group=%(security_group)s "
                  "default_sg=%(default_sg)s ",
                  {'security_group': security_group, 'default_sg': default_sg})

        sg = security_group.get('security_group')
        tenant_id = self._get_tenant_id_for_create(context, sg)
        if not default_sg:
            self._ensure_default_security_group(context, tenant_id)

        # Create the Neutron sg first
        with context.session.begin(subtransactions=True):
            sg = super(MidonetMixin, self).create_security_group(
                context, security_group, default_sg)
            self.client.create_security_group_precommit(context, sg)

        try:
            self.client.create_security_group_postcommit(sg)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create MidoNet resources for "
                              "sg %(sg)r, error=%(err)r"),
                          {"sg": sg, "err": ex})
                try:
                    self.delete_security_group(context, sg['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete a security group %s"),
                                  sg['id'])

        LOG.debug("MidonetMixin.create_security_group exiting: sg=%r", sg)
        return sg

    def delete_security_group(self, context, id):
        LOG.debug("MidonetMixin.delete_security_group called: id=%s", id)

        sg = super(MidonetMixin, self).get_security_group(context, id)
        if not sg:
            raise ext_sg.SecurityGroupNotFound(id=id)

        if sg["name"] == 'default' and not context.is_admin:
            raise ext_sg.SecurityGroupCannotRemoveDefault()

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).delete_security_group(context, id)
            self.client.delete_security_group_precommit(context, id)

        self.client.delete_security_group_postcommit(id)

        LOG.debug("MidonetMixin.delete_security_group exiting: id=%r", id)

    def create_security_group_rule(self, context, security_group_rule):
        LOG.debug("MidonetMixin.create_security_group_rule called: "
                  "security_group_rule=%(security_group_rule)r",
                  {'security_group_rule': security_group_rule})

        with context.session.begin(subtransactions=True):
            rule = super(MidonetMixin, self).create_security_group_rule(
                context, security_group_rule)
            self.client.create_security_group_rule_precommit(context, rule)

        try:
            self.client.create_security_group_rule_postcommit(rule)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE('Failed to create security group rule %(sg)s,'
                          'error: %(err)s'), {'sg': rule, 'err': ex})
                try:
                    self.delete_security_group_rule(context, rule['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete "
                                      "a security group rule %s"), rule['id'])

        LOG.debug("MidonetMixin.create_security_group_rule exiting: rule=%r",
                  rule)
        return rule

    def create_security_group_rule_bulk(self, context, rules):
        LOG.debug("MidonetMixin.create_security_group_rule_bulk called: "
                  "security_group_rules=%(security_group_rules)r",
                  {'security_group_rules': rules})

        with context.session.begin(subtransactions=True):
            rules = super(
                MidonetMixin, self).create_security_group_rule_bulk_native(
                    context, rules)
            self.client.create_security_group_rule_bulk_precommit(context,
                                                                  rules)

        try:
            self.client.create_security_group_rule_bulk_postcommit(rules)
        except Exception as ex:
            LOG.error(_LE("Failed to create bulk security group rules %(sg)s, "
                          "error: %(err)s"), {"sg": rules, "err": ex})
            with excutils.save_and_reraise_exception():
                for rule in rules:
                    self.delete_security_group_rule(context, rule['id'])

        LOG.debug("MidonetMixin.create_security_group_rule_bulk exiting: "
                  "rules=%r", rules)
        return rules

    def delete_security_group_rule(self, context, sg_rule_id):
        LOG.debug("MidonetMixin.delete_security_group_rule called: "
                  "sg_rule_id=%s", sg_rule_id)

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).delete_security_group_rule(context,
                                                                 sg_rule_id)
            self.client.delete_security_group_rule_precommit(context,
                                                             sg_rule_id)

        self.client.delete_security_group_rule_postcommit(sg_rule_id)

        LOG.debug("MidonetMixin.delete_security_group_rule exiting: id=%r",
                  id)

    def create_agent_membership(self, context, agent_membership):
        LOG.debug("MidonetMixin.create_agent_membership called: "
                  " %(agent_membership)r",
                  {'agent_membership': agent_membership})

        with context.session.begin(subtransactions=True):
            am = super(MidonetMixin, self).create_agent_membership(
                context, agent_membership)
            self.client.create_agent_membership_precommit(context, am)

        try:
            self.client.create_agent_membership_postcommit(am)
        except Exception as ex:
            with excutils.save_and_reraise_exception():
                LOG.error(_LE("Failed to create agent membership. am: %(am)r, "
                              "error: %(err)s"), {'am': am, 'err': ex})
                try:
                    self.delete_agent_membership(context, am['id'])
                except Exception:
                    LOG.exception(_LE("Failed to delete "
                                      "an agent membership %s"), am['id'])

        LOG.debug("MidonetMixin.create_agent_membership exiting: "
                  "%(agent_membership)r", {'agent_membership': am})
        return am

    def get_agent_membership(self, context, id, filters=None, fields=None):
        LOG.debug("MidonetMixin.get_agent_membership called: id=%(id)r",
                  {'id': id})

        with context.session.begin(subtransactions=True):
            am = super(MidonetMixin, self).get_agent_membership(context, id)

        LOG.debug("MidonetMixin.get_agent_membership exiting: id=%(id)r, "
                  "agent_membership=%(agent_membership)r",
                  {'id': id, 'agent_membership': am})
        return am

    def get_agent_memberships(self, context, filters=None, fields=None,
                              sorts=None, limit=None, marker=None,
                              page_reverse=False):
        LOG.debug("MidonetMixin.get_agent_memberships called")

        with context.session.begin(subtransactions=True):
            ams = super(MidonetMixin, self).get_agent_memberships(
                context, filters, fields, sorts, limit, marker, page_reverse)

        LOG.debug("MidonetMixin.get_agent_memberships exiting")
        return ams

    def delete_agent_membership(self, context, id):
        LOG.debug("MidonetMixin.delete_agent_membership called: %(id)r",
                  {'id': id})

        with context.session.begin(subtransactions=True):
            super(MidonetMixin, self).delete_agent_membership(context, id)
            self.client.delete_agent_membership_precommit(context, id)

        self.client.delete_agent_membership_postcommit(id)

        LOG.debug("MidonetMixin.delete_agent_membership exiting: %(id)r",
                  {'id': id})

    def get_agents(self, context, filters=None, fields=None):
        LOG.debug("MidonetMixin.get_agents called")

        agents = super(MidonetMixin, self).get_agents(context, filters, fields)
        return agents + self.client.get_agents()

    def get_agent(self, context, id, fields=None):
        LOG.debug("MidonetMixin.get_agent called: %(id)r", {'id': id})

        agent = self.client.get_agent(id)
        if not agent:
            agent = super(MidonetMixin, self).get_agent(context, id, fields)
        return agent
