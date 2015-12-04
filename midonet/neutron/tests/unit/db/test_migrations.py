# Copyright (c) 2015 Cisco Systems, Inc.
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

from oslo_config import cfg

from neutron.db.migration.alembic_migrations import external
from neutron.db.migration import cli as migration
from neutron.tests.common import base
from neutron.tests.functional.db import test_migrations

#from midonet.neutron.db.migration import alembic_migrations
from midonet.neutron.db.migration.models import head

# List of *aaS tables to exclude
# REVISIT(yamamoto): These *aaS repos should provide the lists by themselves,
# similarly to Neutron's external.TABLES.

LBAAS_TABLES = {
    'alembic_version_lbaas',

    # bug 1522706
    'lbaas_listeners',
    'lbaas_sni',

    # NOTE(yamamoto): We don't import these models
    'nsxv_edge_monitor_mappings',
    'nsxv_edge_pool_mappings',
    'nsxv_edge_vip_mappings',
}

FWAAS_TABLES = {
    'alembic_version_fwaas',

    # NOTE(yamamoto): We don't import these models
    'cisco_firewall_associations',
}

# EXTERNAL_TABLES should contain all names of tables that are not related to
# current repo.
EXTERNAL_TABLES = set(external.TABLES) | LBAAS_TABLES | FWAAS_TABLES
VERSION_TABLE = 'alembic_version_midonet'


class _TestModelsMigrationsMidonet(test_migrations._TestModelsMigrations):

    def db_sync(self, engine):
        cfg.CONF.set_override('connection', engine.url, group='database')
        for conf in migration.get_alembic_configs():
            self.alembic_config = conf
            self.alembic_config.neutron_config = cfg.CONF
            migration.do_alembic_command(conf, 'upgrade', 'heads')

    def get_metadata(self):
        return head.get_metadata()

    def include_object(self, object_, name, type_, reflected, compare_to):
        if type_ == 'table' and (name == 'alembic' or
                                 name == VERSION_TABLE or
                                 name in EXTERNAL_TABLES):
            return False
        if type_ == 'index' and reflected and name.startswith("idx_autoinc_"):
            return False
        return True


class TestModelsMigrationsMysql(_TestModelsMigrationsMidonet,
                                base.MySQLTestCase):
    pass
