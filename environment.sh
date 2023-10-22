#!/bin/bash

# This is an example environment.sh for local docker deployments.
# It is used for testing epics-contianers-cli. It sets up a number of
# environment varaibles used to direct 'ec' commands to the beamline you
# are working on. Typically each beamline repository will have its own.

# check we are sourced
if [ "$0" = "$BASH_SOURCE" ]; then
    echo "ERROR: Please source this script"
    exit 1
fi

echo "Loading IOC environment for BL45P ..."

# a mapping between genenric IOC repo roots and the related container registry
export EC_REGISTRY_MAPPING='github.com=ghcr.io gitlab.diamond.ac.uk=gcr.io/diamond-privreg/controls/ioc'

# the git rempos used for the current beamline
export EC_DOMAIN_REPO=git@github.com:epics-containers/bl45p.git

# to use kubernetes specify the namespace - otherwise docker local deployments are used
# export EC_K8S_NAMESPACE=bl45p

# enforce a specific container cli (docker or podman)
# export EC_CONTAINER_CLI=podman

# enable debug output in all 'ec' commands
# export EC_DEBUG=1

# declare your centralised log server Web UI
# export EC_LOG_URL='https://graylog2.diamond.ac.uk/search?rangetype=relative&fields=message%2Csource&width=1489&highlightMessage=&relative=172800&q=pod_name%3A{ioc_name}*'

# if you are using kubernetes then this script must enable access to the cluster.
# An example for how this is done at DLS is below.

# # the following configures kubernetes inside DLS.
# if module --version &> /dev/null; then
#     if module avail pollux > /dev/null; then
#         module unload pollux > /dev/null
#         module load pollux > /dev/null
#     fi
# fi

# check if epics-containers-cli (ec command) is installed and install if not
if ! ec --version &> /dev/null; then
    # must be in a venv and this is the reliable check
    if python3 -c 'import sys; sys.exit(0 if sys.base_prefix==sys.prefix else 1)'; then
        echo "ERROR: Please activate a virtualenv and re-run"
        return
    elif ! ec --version &> /dev/null; then
        pip install epics-containers-cli
    fi
fi

# enable shell completion for ec commands
source <(ec --show-completion ${SHELL})
