==================
networking-midonet
==================

This is the official Midonet Neutron plugin.

The current set of supported versions of MidoNet are:

- v2015.03
- v2015.06
- v5.0

NOTE: MidoNet recently changed its versioning scheme.
v5.0 is what used to be called v2015.09.


How to Install
--------------

For productional deployments, we recommend to use a package for your
distribution if available::

    http://builds.midonet.org/

You can install the plugin from the source code by running the following
command::

    $ sudo python setup.py install


Core plugin and L3 service plugin
---------------------------------

The following entry in ``neutron.conf`` enables MidoNet as the Neutron plugin.
There are two plugins to choose from.

Plugin v1, which is compatible with MidoNet v2015.03 and v2015.06::

    [DEFAULT]
    core_plugin = midonet

Plugin v2, which is compatible with MidoNet v5.0 and beyond.
It works with a separate L3 plugin which you need to add to the list of
service plugins::

    [DEFAULT]
    core_plugin = midonet_v2
    service_plugins = midonet_l3


ML2 mechanism and type drivers
------------------------------

Experimental ML2 mechanism driver and type drivers are available.
They are compatible with MidoNet v5.0 and beyond::

    [DEFAULT]
    core_plugin = ml2
    service_plugins = midonet_l3

    [ml2]
    tenant_network_types = midonet
    type_drivers = midonet,uplink
    mechanism_drivers = midonet


Interaction with Neutron agents
-------------------------------

For v2015.03 and v2015.06, OpenStack deployment with MidoNet works with
Neutron DHCP and Metadata agents.

For MidoNet v5.0 and later, no Neutron agents are necessary.

For details, please refer to MidoNet documentation::

    https://docs.midonet.org


LBaaS
-----

To enable LBaaS, enable the service plugin in ``/etc/neutron/neutron.conf``::

    [DEFAULT]
    service_plugins = lbaas

In addition to that, configure service providers as described in
the following sections.


MidoNet native provider
~~~~~~~~~~~~~~~~~~~~~~~

Starting in Kilo, MidoNet implements LBaaS v1 following the advanced
service driver model.  To configure MidoNet as the LBaaS provider, set the
following entries in the Neutron configuration file
``/etc/neutron/neutron.conf``::

    [service_providers]
    service_provider = LOADBALANCER:Midonet:midonet.neutron.services.loadbalancer.driver.MidonetLoadbalancerDriver:default

NOTE: This provider does not use Neutron LBaaS agent.


Haproxy provider
~~~~~~~~~~~~~~~~

With the latest development version MidoNet, you can use "haproxy"
LBaaS provider (and possibly other agent-based providers) with
the following configuration in ``/etc/neutron/neutron.conf``::

    [service_providers]
    service_provider = LOADBALANCER:Haproxy:neutron_lbaas.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver:default

NOTE: This provider requires Neutron LBaaS agent.


Multiple providers
~~~~~~~~~~~~~~~~~~

You can configure multiple providers as the following::

    [service_providers]
    service_provider = LOADBALANCER:Midonet:midonet.neutron.services.loadbalancer.driver.MidonetLoadbalancerDriver:default
    service_provider = LOADBALANCER:Haproxy:neutron_lbaas.services.loadbalancer.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver


FWaaS
-----

Starting v5.0, MidoNet implements Neutron FWaaS extention API.

To configure it, add the following service plugin to the `service_plugins` list
in the DEFAULT section of `neutron.conf`::

    midonet_firewall

NOTE: No need to configure `Firewall Driver` at all.  It's irrelevant
because this plugin does not use Neutron L3 agent.


VPNaaS
------

Starting v5.1, MidoNet implements Neutron VPNaaS extension API.

MidoNet plugin implements VPNaaS as a service driver.  To configure it,
add the following entries in the Neutron configuration file
``/etc/neutron/neutron.conf``::

    [DEFAULT]
    service_plugins = vpnaas

    [service_providers]
    service_provider=VPN:Midonet:midonet.neutron.services.vpn.service_drivers.midonet_ipsec.MidonetIPsecVPNDriver:default

NOTE: This plugin does not use Neutron VPNaaS agent.
