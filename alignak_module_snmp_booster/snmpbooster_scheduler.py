# -*- coding: utf-8 -*-
# pylint: disable=fixme
#
# Copyright (C) 2015-2016: Alignak contrib team, see AUTHORS.txt file for contributors
#
# This file is part of Alignak contrib projet.
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
#
# This file incorporates work covered by the following copyright and
# permission notice:
#
# Copyright (C) 2012-2014:
#    Thibault Cohen, thibault.cohen@savoirfairelinux.com
#
# This file is part of SNMP Booster Shinken Module.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with SNMP Booster Shinken Module.
# If not, see <http://www.gnu.org/licenses/>.


"""
This module contains the SnmpBoosterScheduler class which is the part
of SNMP Booster loaded in the Scheduler
"""

import logging

from snmpbooster import SnmpBooster

logger = logging.getLogger('alignak.module')  # pylint: disable=C0103


properties = {
    'daemons': ['scheduler'],
    'type': 'snmp_booster',
    'external': False,
    'phases': ['running', 'late_configuration'],
    # To be a real worker module, you must set this
    'worker_capable': True,
}


def get_instance(mod_conf):
    """
    Return a module instance for the modules manager

    :param mod_conf: the module properties as defined globally in this file
    :return:
    """
    logger.info("Give an instance of %s for alias: %s", mod_conf.python_name, mod_conf.module_alias)
    logger.info("[SnmpBooster] [code 0101] Loading SNMP Booster module "
                "for plugin %s" % mod_conf.get_name())
    # Check if the attribute loaded_by is set
    if not hasattr(mod_conf, 'loaded_by'):
        message = ("[SnmpBooster] [code 0102] Couldn't find 'loaded_by' "
                   "configuration directive.")
        logger.error(message)
        raise Exception(message)
    # Check if the attribute loaded_by is correctly used
    if mod_conf.loaded_by not in mod_conf.properties['daemons']:
        message = ("[SnmpBooster] [code 0103] 'loaded_by' attribute must be "
                   "in %s" % str(mod_conf.properties['daemons']))
        logger.error(message)
        raise Exception(message)

    # Get class name (arbiter, scheduler or poller)
    class_name = "SnmpBooster%s" % mod_conf.loaded_by.capitalize()
    # Instance it
    instance = globals()[class_name](mod_conf)
    # Return it
    return instance


class SnmpBoosterScheduler(SnmpBooster):
    """ SNMP Poller module class
        Improve SNMP checks
    """
    def __init__(self, mod_conf):
        """
        Module initialization

        mod_conf is a dictionary that contains:
        - all the variables declared in the module configuration file
        - a 'properties' value that is the module properties as defined globally in this file

        :param mod_conf: module configuration file as a dictionary
        """
        SnmpBooster.__init__(self, mod_conf)

        # pylint: disable=global-statement
        global logger
        logger = logging.getLogger('alignak.module.%s' % self.alias)

        logger.debug("inner properties: %s", self.__dict__)
        logger.debug("received configuration: %s", mod_conf.__dict__)
        logger.debug("loaded into: %s", self.loaded_into)

        self.last_check_mapping = {}
        self.offset_mapping = {}

    @staticmethod
    def get_frequence(chk):
        """ return check_interval if state type is HARD
        else retry_interval if state type is SOFT
        """
        if chk.ref.state_type == 'HARD':
            return chk.ref.check_interval
        else:
            return chk.ref.retry_interval

    @staticmethod
    def set_true_check(check, real=False):
        """ Add -r option to the command line """
        if real:
            check.command = check.command + " -r"
        else:
            if check.command.endswith(" -r"):
                check.command = check.command[:-3]

    def hook_get_new_actions(self, sche):
        """ Set if is a SNMP or Cache check """
        # Get all snmp checks and sort checks by tuple (host, interval)
        check_by_host_inter = [((c.ref.host.get_name(),
                                 self.get_frequence(c)
                                 ),
                                c)
                               for c in sche.checks.values()
                               if c.module_type == 'snmp_booster'
                               and c.status == 'scheduled']
        # Sort checks by t_to_go
        check_by_host_inter.sort(key=lambda c: c[1].t_to_go)
        # Elect a check to be a real snmp check
        for key, chk in check_by_host_inter:
            # get frequency
            _, serv_interval = key
            freq = serv_interval * chk.ref.interval_length
            # Check if the key if already defined on last_check_mapping
            # and if the next check is scheduled after the saved
            # timestamps for the key (host, frequency)
            if key in self.last_check_mapping and self.last_check_mapping[key][0] + freq > chk.t_to_go:
                if self.last_check_mapping[key][1] == chk.ref.id:
                    # We don't want to unelected an elected check
                    continue
                # None elected
                # Set none Elected
                self.set_true_check(chk, False)
                continue
            # Elected
            # Saved the new timestamp
            if key not in self.last_check_mapping:
                # Done to smooth check over the interval of freq.
                # We remember the offset for a specific interval and move the elected (real) check to this time
                if serv_interval not in self.offset_mapping:
                    self.offset_mapping[serv_interval] = 0
                self.last_check_mapping[key] = (chk.t_to_go - chk.t_to_go % freq + self.offset_mapping[serv_interval], chk.ref.id)
                self.offset_mapping[serv_interval] = (self.offset_mapping[serv_interval] + 1) % freq
            else:
                self.last_check_mapping[key] = (self.last_check_mapping[key][0] + freq,
                                                chk.ref.id)
                chk.t_to_go = self.last_check_mapping[key][0]
            # Set Elected
            self.set_true_check(chk, True)
