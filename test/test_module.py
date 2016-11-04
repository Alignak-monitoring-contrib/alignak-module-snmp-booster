#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016: Alignak team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak.
#
# Alignak is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alignak is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Alignak.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Test the module
"""

import re

from alignak_test import AlignakTest, time_hacker
from alignak.modulesmanager import ModulesManager
from alignak.objects.module import Module
from alignak.basemodule import BaseModule

import alignak_module_snmp_booster


class TestModuleSnmpBooster(AlignakTest):
    """
    This class contains the tests for the module
    """

    def test_module_loading(self):
        """
        Alignak module loading

        :return:
        """
        self.print_header()
        self.setup_with_file('./cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)
        self.show_configuration_logs()

        # An arbiter module
        modules = [m.module_alias for m in self.arbiter.myself.modules]
        self.assertListEqual(modules, ['SnmpBoosterArbiter'])

        # No broker module
        modules = [m.module_alias for m in self.brokers['broker-master'].modules]
        self.assertListEqual(modules, [])

        # A poller module
        modules = [m.module_alias for m in self.pollers['poller-master'].modules]
        self.assertListEqual(modules, ['SnmpBoosterPoller'])

        # No receiver module
        modules = [m.module_alias for m in self.receivers['receiver-master'].modules]
        self.assertListEqual(modules, [])

        # No reactionner module
        modules = [m.module_alias for m in self.reactionners['reactionner-master'].modules]
        self.assertListEqual(modules, [])

        # A scheduler module
        modules = [m.module_alias for m in self.schedulers['scheduler-master'].modules]
        self.assertListEqual(modules, ['SnmpBoosterScheduler'])

    def test_module_manager_arbiter(self):
        """
        Test if the module manager manages correctly all the modules
        :return:
        """
        self.print_header()
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)

        time_hacker.set_real_time()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'SnmpBoosterArbiter',
            'module_types': 'checks',
            'python_name': 'alignak_module_snmp_booster.snmpbooster_arbiter',
            'loaded_by': 'arbiter',
            'datasource': './cfg/genDevConfig/example.ini',
            'db_host': 'localhost',
            'db_port': 6379
        })

        # Create the modules manager for a daemon type
        self.modulemanager = ModulesManager('arbiter', None)

        # Clear logs
        self.clear_logs()

        # Load and initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        # Loading module logs
        self.assert_log_match(re.escape(
            "Importing Python module 'alignak_module_snmp_booster.snmpbooster_arbiter' for "
            "SnmpBoosterArbiter..."
        ), 0)
        self.assert_log_match(re.escape(
            "Module properties: {'daemons': ['arbiter'], 'phases': ['running', "
            "'late_configuration'], 'type': 'snmp_booster', 'external': False, "
            "'worker_capable': True}"
        ), 1)
        self.assert_log_match(re.escape(
            "Imported 'alignak_module_snmp_booster.snmpbooster_arbiter' for SnmpBoosterArbiter"
        ), 2)
        self.assert_log_match(re.escape(
            "Loaded Python module 'alignak_module_snmp_booster.snmpbooster_arbiter' "
            "(SnmpBoosterArbiter)"
        ), 3)
        self.assert_log_match(re.escape(
            "Give an instance of alignak_module_snmp_booster.snmpbooster_arbiter "
            "for alias: SnmpBoosterArbiter"
        ), 4)

        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 0101] Loading SNMP Booster module for plugin SnmpBoosterArbiter"
        ), 5)
        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 0902] Reading input configuration file: "
            "./cfg/genDevConfig/example.ini"
        ), 6)

        # Starting internal module logs
        self.assert_log_match(re.escape(
            "Trying to initialize module: SnmpBoosterArbiter"
        ), 7)
        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 1101] Initialization of the SNMP Booster 2.0.0"
        ), 8)

        my_module = self.modulemanager.instances[0]

        # Get list of not external modules
        self.assertListEqual([my_module], self.modulemanager.get_internal_instances())
        for phase in ['configuration', 'retention']:
            self.assertListEqual([], self.modulemanager.get_internal_instances(phase))
        for phase in ['late_configuration', 'running']:
            self.assertListEqual([my_module], self.modulemanager.get_internal_instances(phase))

        # Get list of external modules
        self.assertListEqual([], self.modulemanager.get_external_instances())
        for phase in ['configuration', 'late_configuration', 'running', 'retention']:
            self.assertListEqual([], self.modulemanager.get_external_instances(phase))

        # Clear logs
        self.clear_logs()

        # Nothing special ...
        self.modulemanager.check_alive_instances()

        # And we clear all now
        self.modulemanager.stop_all()

    def test_module_manager_scheduler(self):
        """
        Test if the module manager manages correctly all the modules
        :return:
        """
        self.print_header()
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)

        time_hacker.set_real_time()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'SnmpBoosterScheduler',
            'module_types': 'checks',
            'python_name': 'alignak_module_snmp_booster.snmpbooster_scheduler',
            'loaded_by': 'scheduler',
            'datasource': './cfg/genDevConfig/example.ini',
            'db_host': 'localhost',
            'db_port': 6379
        })

        # Create the modules manager for a daemon type
        self.modulemanager = ModulesManager('scheduler', None)

        # Clear logs
        self.clear_logs()

        # Load and initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        # Loading module logs
        self.assert_log_match(re.escape(
            "Importing Python module 'alignak_module_snmp_booster.snmpbooster_scheduler' "
            "for SnmpBoosterScheduler..."
        ), 0)
        self.assert_log_match(re.escape(
            "Module properties: {'daemons': ['scheduler'], 'phases': ['running', "
            "'late_configuration'], 'type': 'snmp_booster', 'external': False, "
            "'worker_capable': True}"
        ), 1)
        self.assert_log_match(re.escape(
            "Imported 'alignak_module_snmp_booster.snmpbooster_scheduler' for SnmpBoosterScheduler"
        ), 2)
        self.assert_log_match(re.escape(
            "Loaded Python module 'alignak_module_snmp_booster.snmpbooster_scheduler' "
            "(SnmpBoosterScheduler)"
        ), 3)
        self.assert_log_match(re.escape(
            "Give an instance of alignak_module_snmp_booster.snmpbooster_scheduler "
            "for alias: SnmpBoosterScheduler"
        ), 4)

        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 0101] Loading SNMP Booster module for plugin SnmpBoosterScheduler"
        ), 5)

        # Starting internal module logs
        self.assert_log_match(re.escape(
            "Trying to initialize module: SnmpBoosterScheduler"
        ), 6)
        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 1101] Initialization of the SNMP Booster 2.0.0"
        ), 7)

        my_module = self.modulemanager.instances[0]

        # Get list of not external modules
        self.assertListEqual([my_module], self.modulemanager.get_internal_instances())
        for phase in ['configuration', 'retention']:
            self.assertListEqual([], self.modulemanager.get_internal_instances(phase))
        for phase in ['late_configuration', 'running']:
            self.assertListEqual([my_module], self.modulemanager.get_internal_instances(phase))

        # Get list of external modules
        self.assertListEqual([], self.modulemanager.get_external_instances())
        for phase in ['configuration', 'late_configuration', 'running', 'retention']:
            self.assertListEqual([], self.modulemanager.get_external_instances(phase))

        # Clear logs
        self.clear_logs()

        # Nothing special ...
        self.modulemanager.check_alive_instances()

        # And we clear all now
        self.modulemanager.stop_all()

    def test_module_manager_poller(self):
        """
        Test if the module manager manages correctly all the modules
        :return:
        """
        self.print_header()
        self.setup_with_file('cfg/cfg_default.cfg')
        self.assertTrue(self.conf_is_correct)

        time_hacker.set_real_time()

        # Create an Alignak module
        mod = Module({
            'module_alias': 'SnmpBoosterPoller',
            'module_types': 'checks',
            'python_name': 'alignak_module_snmp_booster.snmpbooster_poller',
            'loaded_by': 'poller',
            'datasource': './cfg/genDevConfig/example.ini',
            'db_host': 'localhost',
            'db_port': 6379
        })

        # Create the modules manager for a daemon type
        self.modulemanager = ModulesManager('poller', None)

        # Clear logs
        self.clear_logs()

        # Load and initialize the modules:
        #  - load python module
        #  - get module properties and instances
        self.modulemanager.load_and_init([mod])

        # Loading module logs
        self.assert_log_match(re.escape(
            "Importing Python module 'alignak_module_snmp_booster.snmpbooster_poller' "
            "for SnmpBoosterPoller..."
        ), 0)
        self.assert_log_match(re.escape(
            "Module properties: {'daemons': ['poller'], 'phases': ['running', "
            "'late_configuration'], 'type': 'snmp_booster', 'external': False, "
            "'worker_capable': True}"
        ), 1)
        self.assert_log_match(re.escape(
            "Imported 'alignak_module_snmp_booster.snmpbooster_poller' for SnmpBoosterPoller"
        ), 2)
        self.assert_log_match(re.escape(
            "Loaded Python module 'alignak_module_snmp_booster.snmpbooster_poller' "
            "(SnmpBoosterPoller)"
        ), 3)
        self.assert_log_match(re.escape(
            "Give an instance of alignak_module_snmp_booster.snmpbooster_poller "
            "for alias: SnmpBoosterPoller"
        ), 4)

        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 0101] Loading SNMP Booster module for plugin SnmpBoosterPoller"
        ), 5)

        # Starting internal module logs
        self.assert_log_match(re.escape(
            "Trying to initialize module: SnmpBoosterPoller"
        ), 6)
        self.assert_log_match(re.escape(
            "[SnmpBooster] [code 1101] Initialization of the SNMP Booster 2.0.0"
        ), 7)

        my_module = self.modulemanager.instances[0]

        # Get list of not external modules
        self.assertListEqual([my_module], self.modulemanager.get_internal_instances())
        for phase in ['configuration', 'retention']:
            self.assertListEqual([], self.modulemanager.get_internal_instances(phase))
        for phase in ['late_configuration', 'running']:
            self.assertListEqual([my_module], self.modulemanager.get_internal_instances(phase))

        # Get list of external modules
        self.assertListEqual([], self.modulemanager.get_external_instances())
        for phase in ['configuration', 'late_configuration', 'running', 'retention']:
            self.assertListEqual([], self.modulemanager.get_external_instances(phase))

        # Clear logs
        self.clear_logs()

        # Nothing special ...
        self.modulemanager.check_alive_instances()

        # And we clear all now
        self.modulemanager.stop_all()

