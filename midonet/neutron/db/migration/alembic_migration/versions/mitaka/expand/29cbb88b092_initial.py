# Copyright 2015 Midokura SARL
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

"""initial

Revision ID: 29cbb88b092
Revises: 422da2897701
Create Date: 2015-11-20 15:16:18.501828

"""

from neutron.db.migration import cli


# revision identifiers, used by Alembic.
revision = '29cbb88b092'
down_revision = '422da2897701'
branch_labels = (cli.EXPAND_BRANCH,)


def upgrade():
    pass
