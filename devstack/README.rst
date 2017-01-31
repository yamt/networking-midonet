========================
DevStack external plugin
========================


To Run DevStack with Full OpenStack Environment
-----------------------------------------------

1. Download DevStack
2. Prepare ``local.conf``
3. Run ``stack.sh``

There are more detailed info on the wiki.
https://github.com/midonet/midonet/wiki/Devstack


To Run DevStack with monolithic midonet plugin
-----------------------------------------------

1. Download DevStack
2. Copy the sample ``midonet/local.conf.sample`` file over to the devstack
   directory as ``local.conf``.
3. Run ``stack.sh``


To Run DevStack with ML2 and midonet mechanism driver
-----------------------------------------------------

1. Download DevStack
2. Copy the sample ``ml2/local.conf.sample`` file over to the devstack directory
   as ``local.conf``.
3. Run ``stack.sh``

Note that with these configurations, only the following services are started::

    rabbit
    mysql
    keystone
    nova
    glance
    neutron
    lbaas
    tempest
    horizon


MidoNet backend communication
-----------------------------

MidoNet exposes two ways to communicate to its service:

1. REST (synchronous)
2. Tasks DB (asynchronous - experimental)

By default, the plugin is configured to use the REST API service.
The REST API client is specified as::

    MIDONET_CLIENT=midonet.neutron.client.api.MidonetApiClient

If you want to use the experimental Tasks based API, set the following::

    MIDONET_CLIENT=midonet.neutron.client.cluster.MidonetClusterClient


FWaaS
-----

MidoNet implements Neutron FWaaS extension API.
To configure it with devstack, make sure the following is defined
in ``local.conf``::

    enable_plugin neutron-fwaas https://github.com/openstack/neutron-fwaas
    enable_service q-fwaas
    FWAAS_PLUGIN=midonet_firewall


VPNaaS
------

Starting v5.1, MidoNet implements Neutron VPNaaS extension API.
To configure MidoNet as the VPNaaS driver when running devstack, make sure the
following is defined in ``local.conf``::

    enable_plugin neutron-vpnaas https://github.com/openstack/neutron-vpnaas
    enable_service neutron-vpnaas
    NEUTRON_VPNAAS_SERVICE_PROVIDER="VPN:Midonet:midonet.neutron.services.vpn.service_drivers.midonet_ipsec.MidonetIPsecVPNDriver:default"

NOTE: Currently, this devstack plugin doesn't install ipsec package "libreswan".
Please install it manually.


Gateway Device Management Service
---------------------------------

Starting v5.1, MidoNet implements
Neutron Gateway Device Management Service extension API.
To configure MidoNet including Gateway Device Management Service
when running devstack, make sure the following is defined in ``local.conf``::

    Q_SERVICE_PLUGIN_CLASSES=midonet_gwdevice


L2 Gateway Management Service
---------------------------------

Starting v5.1, MidoNet implements
Neutron L2 Gateway Management Service extension API.
To configure MidoNet including L2 Gateway Management Service
when running devstack, make sure the following is defined in ``local.conf``::

    enable_plugin networking-l2gw https://github.com/openstack/networking-l2gw
    enable_service l2gw-plugin
    Q_PLUGIN_EXTRA_CONF_PATH=/etc/neutron
    Q_PLUGIN_EXTRA_CONF_FILES=(l2gw_plugin.ini)
    L2GW_PLUGIN="midonet_l2gw"
    NETWORKING_L2GW_SERVICE_DRIVER="L2GW:Midonet:midonet.neutron.services.l2gateway.service_drivers.l2gw_midonet.MidonetL2gwDriver:default"


BGP dynamic routing service
---------------------------

Starting v5.2, MidoNet implements Neutron BGP dynamic routing service extension API.
The implementation differs slightly from upstream.
In MidoNet, router treated as bgp-speaker must be specified.

To configure MidoNet including BGP dynamic routing service
when running devstack, make sure the following is defined in ``local.conf``::

    Q_SERVICE_PLUGIN_CLASSES=midonet_bgp


Logging Resource Service
------------------------

Starting v5.2, MidoNet implements Neutron Logging Resource Service extension API.

To configure MidoNet including Logging Resource Service when running devstack,
make sure the following is defined in ``local.conf``::

    Q_SERVICE_PLUGIN_CLASSES=midonet_logging_resource

QoS
---

The following ``local.conf`` snippet would enable QoS extension with
MidoNet driver::

    enable_plugin neutron https://github.com/openstack/neutron
    enable_service q-qos
    disable_service q-trunk  # bug 1643451


LBaaS v2
--------

The following ``local.conf`` snippet would enable LBaaS v2 extension with
MidoNet driver::

    enable_plugin neutron-lbaas https://git.openstack.org/openstack/neutron-lbaas
    enable_service q-lbaasv2
    NEUTRON_LBAAS_SERVICE_PROVIDERV2="LOADBALANCERV2:Midonet:midonet.neutron.services.loadbalancer.v2_driver.MidonetLoadBalancerDriver:default"
