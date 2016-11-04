Alignak SNMP booster Module
===========================

*Alignak SNMP booster module*

----------------------------------------------------------
**WARNING: this module is still a very draft version !!!**
----------------------------------------------------------

Build status (stable release)
-----------------------------

.. image:: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-snmp-booster.svg?branch=master
    :target: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-snmp-booster


Build status (development release)
----------------------------------

.. image:: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-snmp-booster.svg?branch=develop
    :target: https://travis-ci.org/Alignak-monitoring-contrib/alignak-module-snmp-booster


Short description
-----------------

This module allows Alignak Pollers to bypass the launch of an SNMP get for each requested OID.

For more information see the project documentation.

Installation
------------

Requirements
~~~~~~~~~~~~


From PyPI
~~~~~~~~~
To install the module from PyPI:
::

    pip install alignak-module-snmp-booster


From source files
~~~~~~~~~~~~~~~~~
To install the module from the source files:
::

    git clone https://github.com/Alignak-monitoring-contrib/alignak-module-snmp-booster
    cd alignak-module-snmp-booster
    pip install -r requirements
    python setup.py install


Configuration
-------------

Once installed, this module has its own configuration file in the */usr/local/etc/alignak/arbiter/modules* directory.
The default configuration file is *mod-snmp-booster.cfg*.

Configure the Alignak arbiter to use this module:

    - edit your poller daemon configuration file
    - add the `module_alias` parameter value (`SnmpBoosterArbiter`) to the `modules` parameter of the daemon

Configure an Alignak scheduler to use this module:

    - edit your poller daemon configuration file
    - add the `module_alias` parameter value (`SnmpBoosterScheduler`) to the `modules` parameter of the daemon

Configure an Alignak poller to use this module:

    - edit your poller daemon configuration file
    - add the `module_alias` parameter value (`SnmpBoosterPoller`) to the `modules` parameter of the daemon


Tag the NRPE commands with the `module_type` parameter. This parameter must be the `module_alias` of the installed module::

    define command {
        command_name    check_snmp
        command_line    $USER1$/check_snmp -H $HOSTADRESS$ -c $ARG1$ -a $ARG2$
        module_type     SnmpBoosterPoller
    }



Bugs, issues and contributing
-----------------------------

Please report any issue using the project `GitHub repository: <https://github.com/Alignak-monitoring-contrib/alignak-module-snmp-booster/issues>`_.

License
-------

Alignak Module External commands is available under the `GPL version 3 license`_.

.. _GPL version 3 license: http://opensource.org/licenses/GPL-3.0
.. _Alignak monitoring contrib: https://github.com/Alignak-monitoring-contrib
.. _PyPI repository: <https://pypi.python.org/pypi>
