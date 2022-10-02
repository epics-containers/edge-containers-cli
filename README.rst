epics-containers-cli
===========================

|code_ci| |docs_ci| |coverage| |pypi_version| |license|

A simple CLI with shortcuts for common operations when developing epics-containers
projects.

============== ==============================================================
PyPI           ``pip install epics-containers-cli``
Source code    https://github.com/epics-containers/epics-containers-cli
Documentation  https://epics-containers.github.io/epics-containers-cli
Releases       https://github.com/epics-containers/epics-containers-cli/releases
============== ==============================================================


An example invocation. Calling the deploy command will execute helm and prints 
the helm command that it makes ::

    $ ec deploy bl45p-mo-ioc-01 0.0.1-b0
    + helm upgrade --install bl45p-mo-ioc-01 oci://ghcr.io/epics-
    containers/bl45p-mo-ioc-01 --version 0.0.1-b0

.. |code_ci| image:: https://github.com/epics-containers/epics-containers-cli/actions/workflows/code.yml/badge.svg?branch=main
    :target: https://github.com/epics-containers/epics-containers-cli/actions/workflows/code.yml
    :alt: Code CI

.. |docs_ci| image:: https://github.com/epics-containers/epics-containers-cli/actions/workflows/docs.yml/badge.svg?branch=main
    :target: https://github.com/epics-containers/epics-containers-cli/actions/workflows/docs.yml
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/epics-containers/epics-containers-cli/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/epics-containers/epics-containers-cli
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/epics-containers-cli.svg
    :target: https://pypi.org/project/epics-containers-cli
    :alt: Latest PyPI version

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://epics-containers.github.io/epics-containers-cli for more detailed documentation.
