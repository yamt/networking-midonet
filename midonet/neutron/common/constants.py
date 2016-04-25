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

# MidoNet Network Type constants
TYPE_UPLINK = 'uplink'
TYPE_MIDONET = 'midonet'

MIDONET_NET_TYPES = [TYPE_MIDONET, TYPE_UPLINK]

# Midonet VIF TYPE
VIF_TYPE_MIDONET = 'midonet'

# Neutron well-known service type constants:
GATEWAY_DEVICE = "GATEWAY_DEVICE"

# for Midonet L2 Gateway
MAX_VXLAN_VNI = 16777215
MIDONET_L2GW_PROVIDER = "midonet"

# (Kengo) We define constants until
# upstream will deal with router status.
ROUTER_STATUS_ACTIVE = "ACTIVE"
ROUTER_STATUS_ERROR = "ERROR"

# for resource name on callback method
MIDONET_NETWORK = "midonet_network"
