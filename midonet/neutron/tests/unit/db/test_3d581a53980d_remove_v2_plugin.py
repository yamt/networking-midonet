# Copyright 2017 Midokura SARL
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from oslo_db.sqlalchemy import utils as db_utils
from oslo_utils import uuidutils

from neutron.tests.functional.db import test_migrations


class RemoveV2Mixin(object):
    def _create_topology(self, engine, network_type):
        networks = db_utils.get_table(engine, 'networks')
        ports = db_utils.get_table(engine, 'ports')
        portbindingports = db_utils.get_table(engine, 'portbindingports')
        midonet_port_bindings = db_utils.get_table(engine,
            'midonet_port_bindings')
        midonet_network_bindings = db_utils.get_table(engine,
            'midonet_network_bindings')

        network_id = uuidutils.generate_uuid()
        network_dict = dict(id=network_id)
        engine.execute(networks.insert().values(network_dict))
        engine.execute(midonet_network_bindings.insert().values(
            dict(network_id=network_id, network_type=network_type),
        ))

        port_id = uuidutils.generate_uuid()
        port_dict = dict(id=port_id, network_id=network_id)
        engine.execute(ports.insert().values(port_dict))
        host = "host-" + network_type
        engine.execute(portbindingports.insert().values(
            dict(port_id=port_id, host=host),
        ))
        if network_type == "uplink":
            interface_name = "interface-uplink"
            engine.execute(midonet_port_bindings.insert().values(
                dict(port_id=port_id, interface_name=interface_name),
            ))
        else:
            interface_name = None
        return dict(network_id=network_id, port_id=port_id,
                    host=host, interface_name=inteface_name)

    def _pre_upgrade_3d581a53980d(self, engine):
        data = {
            "uplink": self._create_topology(engine, network_type="uplink"),
            "midonet": self._create_topology(engine, network_type="midonet"),
        }
        return data

    def _check_3d581a53980d(self, engine, data):
        networks = db_utils.get_table(engine, 'networks')
        ports = db_utils.get_table(engine, 'ports')
        portbindingports = db_utils.get_table(engine, 'portbindingports')
        midonet_port_bindings = db_utils.get_table(engine,
            'midonet_port_bindings')
        midonet_network_bindings = db_utils.get_table(engine,
            'midonet_network_bindings')
        ml2_port_bindings = db_utils.get_table(engine, 'ml2_port_bindings')
        ml2_port_binding_levels = db_utils.get_table(engine,
            'ml2_port_binding_levels')
        ml2_distributed_port_bindings = db_utils.get_table(engine,
            'ml2_distributed_port_bindings')
        networksegments = db_utils.get_table(engine, 'networksegments')

        for table in (
            midonet_port_bindings,
            midonet_network_bindings,
            portbindingports,
        ):
            rows = engine.execute(table.select()).fetchall()
            self.assertEquals([], rows)


class TestRemoveV2Mysql(RemoveV2Mixin,
                        test_migrations.TestWalkMigrationsMysql):
    pass


class TestRemoveV2MixinPsql(RemoveV2Mixin,
                            test_migrations.TestWalkMigrationsPsql):
    pass
