# Copyright (C) 2012 Midokura Japan K.K.
# Copyright (C) 2013 Midokura PTE LTD
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

import contextlib
import datetime
import functools
import mock
from sqlalchemy.orm import sessionmaker
from webob import exc

from midonet.neutron.client import base as cli_base
from midonet.neutron.common import config  # noqa
from midonet.neutron.db import data_state_db
from midonet.neutron.db import data_version_db as dv_db
from midonet.neutron.db import task_db  # noqa

from neutron import context
from neutron.db import api as db_api
from neutron.extensions import portbindings
from neutron.tests.unit import _test_extension_portbindings as test_bindings
from neutron.tests.unit.api import test_extensions
from neutron.tests.unit.db import test_db_base_plugin_v2 as test_plugin
from neutron.tests.unit.extensions import test_agent
from neutron.tests.unit.extensions import test_extra_dhcp_opt as test_dhcpopts
from neutron.tests.unit.extensions import test_extraroute as test_ext_route
from neutron.tests.unit.extensions import test_l3_ext_gw_mode as test_gw_mode
from neutron.tests.unit.extensions import test_securitygroup as test_sg
from neutron.tests.unit import testlib_api

from oslo_config import cfg
from oslo_utils import uuidutils

from midonet.neutron import plugin as mn_plugin  # noqa

PLUGIN_NAME = 'neutron.plugins.midonet.plugin.MidonetPluginV2'
TEST_MN_CLIENT = ('midonet.neutron.tests.unit.test_midonet_plugin.'
                  'NoopMidonetClient')


class NoopMidonetClient(cli_base.MidonetClientBase):
    """Dummy midonet client used for the unit tests"""
    pass


class MidonetPluginConf(object):
    """Plugin configuration shared across the unit and functional tests.
    """

    plugin_name = PLUGIN_NAME

    @staticmethod
    def setUp(test_case, parent_setup=None):
        """Perform additional configuration around the parent's setUp."""
        cfg.CONF.set_override('client', TEST_MN_CLIENT, group='MIDONET')
        if parent_setup:
            parent_setup()


class MidonetPluginV2TestCase(test_plugin.NeutronDbPluginV2TestCase):

    def setup_parent(self, service_plugins=None, ext_mgr=None):

        # Set up mock for the midonet client to be made available in tests
        patcher = mock.patch(TEST_MN_CLIENT)
        self.client_mock = mock.MagicMock()
        patcher.start().return_value = self.client_mock

        # Ensure that the parent setup can be called without arguments
        # by the common configuration setUp.
        parent_setup = functools.partial(
            super(MidonetPluginV2TestCase, self).setUp,
            plugin=MidonetPluginConf.plugin_name,
            service_plugins=service_plugins,
            ext_mgr=ext_mgr,
        )
        MidonetPluginConf.setUp(self, parent_setup)

    def setUp(self, plugin=None, service_plugins=None, ext_mgr=None):
        self.setup_parent(service_plugins=service_plugins, ext_mgr=ext_mgr)


class TestMidonetNetworksV2(MidonetPluginV2TestCase,
                            test_plugin.TestNetworksV2):
    pass


class TestMidonetSecurityGroup(test_sg.TestSecurityGroups,
                               MidonetPluginV2TestCase):
    pass


class TestMidonetSubnetsV2(MidonetPluginV2TestCase,
                           test_plugin.TestSubnetsV2):
    pass


class TestMidonetPortsV2(MidonetPluginV2TestCase,
                         test_plugin.TestPortsV2):
    pass


class TestMidonetPortBinding(MidonetPluginV2TestCase,
                             test_bindings.PortBindingsTestCase):

    VIF_TYPE = portbindings.VIF_TYPE_MIDONET
    HAS_PORT_FILTER = True

    @contextlib.contextmanager
    def port_with_binding_profile(self, host='host', if_name='if_name'):
        args = {portbindings.PROFILE: {'interface_name': if_name},
                portbindings.HOST_ID: host}
        with test_plugin.optional_ctx(None, self.subnet) as subnet_to_use:
            net_id = subnet_to_use['subnet']['network_id']
            port = self._make_port(self.fmt, net_id,
                                   arg_list=(portbindings.PROFILE,
                                             portbindings.HOST_ID,), **args)
            yield port

    def test_create_mido_portbinding(self):
        keys = [(portbindings.PROFILE, {'interface_name': 'if_name'}),
                (portbindings.HOST_ID, 'host')]
        with self.port_with_binding_profile() as port:
            for k, v in keys:
                self.assertEqual(port['port'][k], v)

    def test_create_mido_portbinding_no_profile_specified(self):
        with self.port() as port:
            self.assertIsNone(port['port'][portbindings.PROFILE])

    def test_create_mido_portbinding_no_host_binding(self):
        # Create a binding when there is no host binding.  This should throw
        # an error.
        with self.network() as net:
            args = {'port': {'tenant_id': net['network']['tenant_id'],
                             'network_id': net['network']['id'],
                             portbindings.PROFILE:
                                 {'interface_name': 'if_name'},
                             portbindings.HOST_ID: None}}
            req = self.new_create_request('ports', args, self.fmt)
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 400)

    def test_create_mido_portbinding_no_interface(self):
        # Create binding with no interface name.  Should return an error.
        with self.network() as net:
            args = {'port': {'tenant_id': net['network']['tenant_id'],
                             'network_id': net['network']['id'],
                             portbindings.PROFILE: {'foo': ''},
                             portbindings.HOST_ID: 'host'}}
            req = self.new_create_request('ports', args, self.fmt)
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 400)

    def test_create_mido_portbinding_bad_interface(self):
        # Create binding with a bad interface name.  Should return an error.
        with self.network() as net:
            args = {'port': {'tenant_id': net['network']['tenant_id'],
                             'network_id': net['network']['id'],
                             portbindings.PROFILE: {'interface_name': ''},
                             portbindings.HOST_ID: 'host'}}
            req = self.new_create_request('ports', args, self.fmt)
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 400)

    def test_update_mido_portbinding(self):
        keys = [(portbindings.HOST_ID, 'host2'),
                (portbindings.PROFILE, {'interface_name': 'if_name2'}),
                ('admin_state_up', False),
                ('name', 'test_port2')]
        with self.port_with_binding_profile() as port:
            args = {
                'port': {portbindings.PROFILE: {'interface_name': 'if_name2'},
                         portbindings.HOST_ID: 'host2',
                         'admin_state_up': False,
                         'name': 'test_port2'}}
            req = self.new_update_request('ports', args, port['port']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.api))
            for k, v in keys:
                self.assertEqual(res['port'][k], v)

    def test_update_mido_portbinding_no_profile_specified(self):
        # Modify binding without specifying the profile.
        keys = [(portbindings.HOST_ID, 'host2'),
                (portbindings.PROFILE, {'interface_name': 'if_name'}),
                ('admin_state_up', False),
                ('name', 'test_port2')]
        with self.port_with_binding_profile() as port:
            args = {'port': {portbindings.HOST_ID: 'host2',
                             'admin_state_up': False,
                             'name': 'test_port2'}}
            req = self.new_update_request('ports', args, port['port']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.api))
            for k, v in keys:
                self.assertEqual(res['port'][k], v)

    def test_update_mido_portbinding_no_host_binding(self):
        # Update a binding when there is no host binding.  This should throw
        # an error.
        with self.port() as port:
            args = {
                'port': {portbindings.PROFILE: {'interface_name': 'if_name2'}}}
            req = self.new_update_request('ports', args, port['port']['id'])
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 400)

    def test_update_mido_portbinding_unbind(self):
        # Unbinding a bound port
        with self.port_with_binding_profile() as port:
            args = {'port': {portbindings.PROFILE: None}}
            req = self.new_update_request('ports', args, port['port']['id'])
            res = self.deserialize(self.fmt, req.get_response(self.api))
            self.assertIsNone(res['port'][portbindings.PROFILE])

    def test_update_mido_portbinding_unbind_already_unbound(self):
        # Unbinding an unbound port results in no-op
        with self.port() as port:
            args = {'port': {portbindings.PROFILE: None}}
            req = self.new_update_request('ports', args, port['port']['id'])
            # Success with profile set to None
            res = self.deserialize(self.fmt, req.get_response(self.api))
            self.assertIsNone(res['port'][portbindings.PROFILE])

    def test_update_mido_portbinding_no_interface(self):
        # Update binding with no interface name.  Should return an error.
        with self.port_with_binding_profile() as port:
            args = {
                'port': {portbindings.PROFILE: {'foo': ''}}}
            req = self.new_update_request('ports', args, port['port']['id'])
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 400)

    def test_update_mido_portbinding_bad_interface(self):
        # Update binding with a bad interface name.  Should return an error.
        with self.port_with_binding_profile() as port:
            args = {
                'port': {portbindings.PROFILE: {'interface_name': ''}}}
            req = self.new_update_request('ports', args, port['port']['id'])
            res = req.get_response(self.api)
            self.assertEqual(res.status_int, 400)


class TestMidonetExtGwMode(test_gw_mode.ExtGwModeIntTestCase,
                           MidonetPluginV2TestCase):

    pass


class TestMidonetExtraDHCPOpts(test_dhcpopts.TestExtraDhcpOpt,
                               MidonetPluginV2TestCase):

    pass


class TestMidonetL3NatExtraRoute(test_ext_route.ExtraRouteDBIntTestCase,
                                 MidonetPluginV2TestCase):

    def test_router_update_gateway_upon_subnet_create_ipv6(self):
        # This test in the parent test class fails because 'create_subnet' and
        # 'update_port' are executed in the same transaction, where within
        # 'update_port', a look up is made on the subnet that has not been
        # committed.  Removing the transaction block in 'create_subnet' makes
        #  the problem go away, but it would make create_subnet_precommit
        # meaningless.  Handle this case when MidoNet supports IPv6
        pass


class TestMidonetDataState(testlib_api.SqlTestCase):

    def setUp(self):
        super(TestMidonetDataState, self).setUp()
        self.session = self.get_session()
        self.session.add(data_state_db.DataState(
            updated_at=datetime.datetime.utcnow(),
            readonly=False))

    def get_session(self):
        engine = db_api.get_engine()
        Session = sessionmaker(bind=engine)
        return Session()

    def test_data_show(self):
        ds = data_state_db.get_data_state(self.session)
        self.assertTrue(ds.id is not None)

    def test_data_state_readonly(self):
        data_state_db.set_readonly(self.session)
        ds = data_state_db.get_data_state(self.session)
        self.assertTrue(ds.readonly)
        # TODO(Joe) - creating tasks should fail here. Implement
        # with further task_db changes coming in data sync
        data_state_db.set_readwrite(self.session)
        ds = data_state_db.get_data_state(self.session)
        self.assertTrue(not ds.readonly)


class TestMidonetAgent(MidonetPluginV2TestCase,
                       test_agent.AgentDBTestMixIn):

    def setUp(self):
        super(TestMidonetAgent, self).setUp()
        self.adminContext = context.get_admin_context()
        ext_mgr = test_agent.AgentTestExtensionManager()
        self.ext_api = test_extensions.setup_extensions_middleware(ext_mgr)

    def test_list_agents_including_midonet_agents(self):
        agents = self._register_agent_states()
        agent1 = {
            'id': uuidutils.generate_uuid(),
            'binary': 'midolman',
            'admin_state_up': True,
            'host': 'midohostA',
            'agent_type': 'Midonet Agent'}

        agent2 = {
            'id': uuidutils.generate_uuid(),
            'binary': 'midolman',
            'admin_state_up': False,
            'host': 'midohostB',
            'agent_type': 'Midonet Agent'}

        self.client_mock.get_agents.return_value = [agent1, agent2]

        res = self._list('agents')
        agent_ids = [ag['id'] for ag in res['agents']]

        self.assertEqual(len(agents) + 2, len(res['agents']))
        self.assertIn(agent1['id'], agent_ids)
        self.assertIn(agent2['id'], agent_ids)

    def test_show_midonet_agent(self):
        self._register_agent_states()

        agent_id = uuidutils.generate_uuid()
        self.client_mock.get_agent.return_value = {
            'id': agent_id,
            'binary': 'midolman',
            'admin_state_up': True,
            'host': 'midohostA',
            'agent_type': 'Midonet Agent'}

        agent = self._show('agents', agent_id)
        self.assertEqual(agent['agent']['id'], agent_id)

    def test_show_non_existent_midonet_agent(self):
        self._register_agent_states()

        self.client_mock.get_agent.return_value = None

        self._show('agents', uuidutils.generate_uuid(),
                   expected_code=exc.HTTPNotFound.code)


class TestMidonetDataVersion(testlib_api.SqlTestCase):

    def get_session(self):
        engine = db_api.get_engine()
        Session = sessionmaker(bind=engine)
        return Session()

    def test_create_version(self):
        session = self.get_session()
        dv_db.create_data_version(session)
        version = dv_db.get_last_version(session)
        self.assertEqual(version.id, 1)
        self.assertEqual(version.sync_tasks_status, dv_db.STARTED)

    def _test_version_status(self, version_update_func, status):
        session = self.get_session()
        dv_db.create_data_version(session)
        version = dv_db.get_last_version(session)
        self.assertEqual(version.sync_tasks_status, dv_db.STARTED)
        version_update_func(session)
        version = dv_db.get_last_version(session)
        self.assertEqual(version.sync_tasks_status, status)

    def test_update_version_status_completed(self):
        self._test_version_status(dv_db.complete_last_version,
                                  dv_db.COMPLETED)

    def test_update_version_status_error(self):
        self._test_version_status(dv_db.error_last_version,
                                  dv_db.ERROR)

    def test_update_version_status_aborted(self):
        self._test_version_status(dv_db.abort_last_version,
                                  dv_db.ABORTED)
