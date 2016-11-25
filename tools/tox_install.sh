#! /bin/sh

set -e

DIR=$(dirname $0)
${DIR}/tox_install_project.sh neutron neutron $*
${DIR}/tox_install_project.sh neutron-fwaas neutron_fwaas $*
${DIR}/tox_install_project.sh neutron-vpnaas neutron_vpnaas $*
${DIR}/tox_install_project.sh neutron-lbaas neutron_lbaas $*
${DIR}/tox_install_project.sh neutron-dynamic-routing neutron_dynamic_routing $*
${DIR}/tox_install_project.sh networking-l2gw networking_l2gw $*
${DIR}/tox_install_project.sh tap-as-a-service neutron_taas $*

CONSTRAINTS_FILE=$1
shift

install_cmd="pip install"
if [ $CONSTRAINTS_FILE != "unconstrained" ]; then
    install_cmd="$install_cmd -c$CONSTRAINTS_FILE"
fi

$install_cmd -U $*
