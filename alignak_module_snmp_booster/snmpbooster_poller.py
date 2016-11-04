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
This module contains the SnmpBoosterPoller class which is the part
of SNMP Booster loaded in the Poller
"""


import sys
import signal
import time
import shlex

import logging

from Queue import Empty, Queue

from datetime import datetime, timedelta

from alignak.util import to_int
from pyasn1.type.univ import OctetString

from snmpbooster import SnmpBooster
from libs.utils import parse_args, compute_value
from libs.result import set_output_and_status
from libs.checks import check_snmp, check_cache
from libs.snmpworker import SNMPWorker

logger = logging.getLogger('alignak.module')  # pylint: disable=C0103


properties = {
    'daemons': ['poller'],
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


class SnmpBoosterPoller(SnmpBooster):
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

        self.max_prepared_tasks = to_int(getattr(mod_conf, 'max_prepared_tasks', 50))
        self.checks_done = 0
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.last_checks_counted = 0

    def get_new_checks(self):
        """ Get new checks if less than nb_checks_max
            If no new checks got and no check in queue,
            sleep for 1 sec
            REF: doc/shinken-action-queues.png (3)
        """
        try:
            while True:
                try:
                    msg = self.master_slave_queue.get(block=False)
                except IOError:
                    # IOError: [Errno 104] Connection reset by peer
                    msg = None
                if msg is not None:
                    self.checks.append(msg.get_data())
        except Empty:
            if len(self.checks) == 0:
                time.sleep(1)

    def launch_new_checks(self):
        """ Launch checks that are in status
            REF: doc/shinken-action-queues.png (4)
        """
        for chk in self.checks:
            now = time.time()
            if chk.status == 'queue':
                # Ok we launch it
                chk.status = 'launched'
                chk.check_time = now

                # Want the args of the commands so we parse it like a shell
                # shlex want str only
                clean_command = shlex.split(chk.command.encode('utf8',
                                                               'ignore'))
                # If the command seems good
                if len(clean_command) > 1:
                    # we do not want the first member, check_snmp thing
                    try:
                        args = parse_args(clean_command[1:])
                    except Exception as exp:
                        # if we get a parsing error
                        error_message = ("[SnmpBooster] [code 1001]"
                                         "Command line { %s } parsing error: "
                                         "%s" % (chk.command.encode('utf8',
                                                                    'ignore'),
                                                 str(exp)))
                        logger.error(error_message)
                        # Check is now marked as done
                        chk.status = 'done'
                        # Get exit code
                        chk.exit_status = 3
                        chk.get_outputs("Command line parsing error: `%s' - "
                                        "Please verify your check "
                                        "command" % str(exp),
                                        8012)
                        # Get execution time
                        chk.execution_time = 0

                        continue

                # Ok we are good, we go on
                if args.get('real_check', False):
                    # Make a SNMP check
                    check_snmp(chk, args, self.db_client,
                               self.task_queue, self.result_queue)
                    #logger.debug("CHECK SNMP %(host)s:%(service)s" % args)
                else:
                    # Make fake check (get datas from DB)
                    check_cache(chk, args, self.db_client)
                    #logger.debug("CHECK cache %(host)s:%(service)s" % args)

    # Check the status of checks
    # if done, return message finished :)
    # REF: doc/shinken-action-queues.png (5)
    def manage_finished_checks(self):
        """ This function handles finished check
        It gets output and exit_code and
        Add check to the return queue
        """
        to_del = []

        now = time.time()
        prev_log = self.last_checks_counted
        if now > prev_log + 5:
            logger.info("%s checks ongoing.." % len(self.checks))
            self.last_checks_counted = now
        # First look for checks in timeout
        for chk in self.checks:
            if now > chk.check_time + 3600:
                logger.warning("check timeout: %s" % chk.command)
                chk.get_outputs("check timedout", 8012)
                chk.status = "done"
                chk.exit_status = 3
                chk.execution_time = now - chk.check_time
            if not hasattr(chk, "result"):
                continue
            if chk.status == 'launched' and chk.result.get('state') != 'received':
                pass
                # TODO compore check.result['execution_time'] > timeout
                # chk.con.look_for_timeout()

        # Now we look for finished checks
        for chk in self.checks:
            # First manage check in error, bad formed
            if chk.status == 'done':
                if hasattr(chk, "result"):
                    del chk.result
                to_del.append(chk)
                try:
                    self.returns_queue.put(chk)
                except IOError, exp:
                    logger.error("[SnmpBooster] [code 1002]"
                                 "[%d] Exiting: %s" % (str(self), exp))
                    # NOTE Do we really want to exit ???
                    sys.exit(2)
                continue
            # Then we check for good checks
            if not hasattr(chk, "result"):
                continue
            if chk.status == 'launched' and chk.result['state'] == 'received':
                result = chk.result
                # Format result
                # Launch trigger
                set_output_and_status(result)
                # Set status
                chk.status = 'done'
                # Get exit code
                chk.exit_status = result.get('exit_code', 3)
                chk.get_outputs(str(result.get('output',
                                               'Output is missing')),
                                8012)
                # Get execution time
                chk.execution_time = result.get('execution_time', 0.0)

                # unlink our object from the original check
                if hasattr(chk, 'result'):
                    del chk.result

                # and set this check for deleting
                # and try to send it
                to_del.append(chk)
                try:
                    self.returns_queue.put(chk)
                except IOError, exp:
                    logger.error("[SnmpBooster] [code 1003]"
                                 "FIX-ME-ID Exiting: %s" % exp)
                    # NOTE Do we really want to exit ???
                    sys.exit(2)

        # And delete finished checks
        for chk in to_del:
            self.checks.remove(chk)
            # Count checks done
            self.checks_done += 1

    def save_results(self):
        """ Save results to database """
        while not self.result_queue.empty():
            results = self.result_queue.get()
            for result in results.values():
                # Check error
                snmp_error = result.get('error')
                # Get key from task
                key = result.get('key')
                if snmp_error is None:
                    # We don't got a SNMP error
                    # Clean raw_value:
                    if result.get('type') in ['DERIVE', 'GAUGE', 'COUNTER']:
                        if isinstance(result.get('value'), OctetString):
                            result['value'] = raw_value = float(str(result.get('value')))
                        else:
                            result['value'] = raw_value = float(result.get('value'))
                    elif result.get('type') in ['DERIVE64', 'COUNTER64']:
                        result['value'] = raw_value = float(result.get('value'))
                    elif result.get('type') in ['TEXT', 'STRING']:
                        result['value'] = raw_value = str(result.get('value'))
                    else:
                        logger.error("[SnmpBooster] [code 1004] [%s, %s] "
                                     "Value type is not in 'TEXT', 'STRING', "
                                     "'DERIVE', 'GAUGE', 'COUNTER', 'DERIVE64'"
                                     ", 'COUNTER64'" % (key.get('host'),
                                                        key.get('service'),
                                                        ))
                        continue
                    # Compute value before saving
                    if key.get('oid_type') == 'ds_oid':
                        # add max value
                        result['ds_max'] = None
                        if results.get(result['ds_max_oid']) is not None:
                            result['ds_max'] = results.get(result['ds_max_oid']).get('value')
                        # add min value
                        result['ds_min'] = None
                        if results.get(result['ds_min_oid']) is not None:
                            result['ds_min'] = results.get(result['ds_min_oid']).get('value')
                        try:
                            value = compute_value(result)
                        except Exception as exp:
                            logger.warning("[SnmpBooster] [code 1005]"
                                           " [%s, %s] "
                                           "%s" % (key.get('host'),
                                                   key.get('service'),
                                                   str(exp)))
                            value = None
                    else:
                        # For oid_type == ds_max or ds_min
                        # No calculation or transformation needed
                        # So value is raw_value
                        value = raw_value
                else:
                    # We got a SNMP error
                    raw_value = None
                    value = None
                # Save to database
                new_data = {"ds": {} }
                for ds_name in key.get('ds_names'):

                    new_data["ds"][ds_name] = {}
                    new_data["ds"][ds_name][key.get('oid_type') + "_value_last"] = result.get('value_last')
                    new_data["ds"][ds_name][key.get('oid_type') + "_value"] = raw_value
                    new_data["ds"][ds_name][key.get('oid_type') + "_value_computed"] = value
                    new_data["ds"][ds_name][key.get('oid_type') + "_value_computed_last"] = result.get('value_last_computed')
                    new_data["ds"][ds_name]["error"] = snmp_error

                new_data["check_time"] = result.get('check_time')
                new_data["check_time_last"] = result.get('check_time_last')

                self.db_client.update_service(key.get('host'), key.get('service'), new_data)
            # Remove task from queue
            self.result_queue.task_done()

    # id = id of the worker
    # master_slave_queue = Global Queue Master->Slave
    # m = Queue Slave->Master
    # return_queue = queue managed by manager
    # control_queue = Control Queue for the worker
    def work(self, master_slave_queue, returns_queue, control_queue):
        """ Main loop of SNMP Booster """
        logger.info("[SnmpBooster] [code 1006] Module SNMP Booster started!")
        # restore default signal handler for the workers:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        timeout = 1.0
        self.checks = []

        self.returns_queue = returns_queue
        self.master_slave_queue = master_slave_queue
        self.t_each_loop = time.time()
        self.snmpworker = SNMPWorker(self.task_queue, self.max_prepared_tasks)
        self.snmpworker.start()

        dt_start = datetime.now()
        dt_mid = dt_start.replace(hour=12, minute=0, second=0, microsecond=0)
        if dt_mid < dt_start:
            dt_mid = dt_mid + timedelta(days=1)
        while True:
            now = datetime.now()
            if 0 and now > dt_mid:
                logger.info('worker leaving..')
                break
            cmsg = None
            # Check snmp worker status
            if not self.snmpworker.is_alive():
                # The snmpworker seems down ...
                # We respawn one
                self.snmpworker.join()
                self.snmpworker = SNMPWorker(self.task_queue, self.max_prepared_tasks)
                # and start it
                self.snmpworker.start()

            # If we are diyin (big problem!) we do not
            # take new jobs, we just finished the current one
            if not self.i_am_dying:
                # Get new checks to do
                self.get_new_checks()
            # Launch checks
            self.launch_new_checks()
            # Save collected datas from checks in mongodb
            self.save_results()
            # Prepare checks output
            self.manage_finished_checks()

            # Now get order from master
            try:
                cmsg = control_queue.get(block=False)
                if cmsg.get_type() == 'Die':
                    # TODO : What is self.id undefined variable
                    # logger.info("[SnmpBooster] [%d]
                    # Dad say we are dying..." % self.id)
                    logger.info("[SnmpBooster] [code 1007] FIX-ME-ID Parent "
                                "requests termination.")
                    break
            except Empty:
                pass

            # TODO : better time management
            time.sleep(.1)
