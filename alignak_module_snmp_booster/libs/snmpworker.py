# -*- coding: utf-8 -*-

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


""" This module contains a class to create a Thread which make SNMP requests
and handle answers with callbacks

"""

from threading import Thread
import re
import time
import logging

logger = logging.getLogger(__name__)  # pylint: disable=C0103


try:
    from pysnmp.entity.rfc3413.oneliner import cmdgen
    from pysnmp.smi.exval import noSuchInstance
except ImportError as exp:
    logger.error("[SnmpBooster] [code 0601] Import error. Pysnmp is missing")
    raise ImportError(exp)


class SNMPWorker(Thread):
    """ Thread which execute all SNMP tasks/requests """
    def __init__(self, mapping_queue, max_prepared_tasks):
        Thread.__init__(self)
        self.cmdgen = None # will be cmdgen.AsynCommandGenerator()
        self.mapping_queue = mapping_queue
        self.max_prepared_tasks = max_prepared_tasks
        self.must_run = False
        self.task_prepared = 0

    def append_task_to_dispatcher(self, snmp_task):
        if snmp_task['type'] in ['bulk', 'next', 'get']:
            # Append snmp requests
            snmp_command_name = ("async" +
                                 snmp_task['type'].capitalize() +
                                 "Cmd")
            getattr(self.cmdgen, snmp_command_name)(**snmp_task['data'])
            # Mark task as done
            self.mapping_queue.task_done()
            self.task_prepared += 1
        else:
            # If the request is not handled
            error_message = ("Bad SNMP requets type: '%s'. Must be "
                             "get, next or bulk." % snmp_task['type'])
            logger.error("[SnmpBooster] [code 0603] [%s] "
                         "%s" % (snmp_task['host'],
                                 error_message))

    def run(self):
        try:
            self.real_run()
        except Exception as err:
            logger.error('SNMPWorker got error: %s' % err)

    def real_run(self):
        """ Process SNMP tasks
        SNMP task is a dict:
        - For a bulk request ::

            {"authData": cmdgen.CommunityData('public')
             "transportTarget": cmdgen.UdpTransportTarget((transportTarget, 161))
             "nonRepeaters": 0
             "maxRepetitions": 64
             "varNames": ['1.3.6.1.2.1.2.2.1.2.0', '...']
             "cbInfo:: (cbFun, (arg1, arg2, ...))
             }

        - For a next request ::

            {"authData": cmdgen.CommunityData('public')
             "transportTarget": cmdgen.UdpTransportTarget((transportTarget, 161))
             "varNames": ['1.3.6.1.2.1.2.2.1.2.0', '...']
             "cbInfo:: (cbFun, (arg1, arg2, ...))
            }

        - For a get request ::

            {"authData": cmdgen.CommunityData('public)
             "transportTarget": cmdgen.UdpTransportTarget((transportTarget, 161))
             "varNames": ['1.3.6.1.2.1.2.2.1.2.0', '...']
             "cbInfo:: (cbFun, (arg1, arg2, ...))
            }
        """
        self.must_run = True
        logger.info("[SnmpBooster] [code 0602] is starting")
        slow_host_waiting = []
        while self.must_run:
            # Prevent memory leak
            del self.cmdgen
            self.cmdgen = cmdgen.AsynCommandGenerator()
            # End prevent memory leak
            self.task_prepared = 0
            # slow host
            slow_host_prepared = []
            # Process slow hosts tasks
            for index, snmp_task in enumerate(slow_host_waiting):
                # Check if we have our max prepared tasks
                if self.task_prepared > self.max_prepared_tasks:
                    break
                # Handle slow hosts
                if snmp_task['no_concurrency']:
                    if snmp_task['host'] in slow_host_prepared:
                        continue
                    else:
                        slow_host_prepared.append(snmp_task['host'])
                # Add task dispatcher
                slow_host_waiting.pop(index)
                self.append_task_to_dispatcher(snmp_task)
            # Process normal tasks
            while (not self.mapping_queue.empty()) and self.task_prepared <= self.max_prepared_tasks:
                # Get task
                snmp_task = self.mapping_queue.get()
                # Handle slow hosts
                if snmp_task['no_concurrency']:
                    if snmp_task['host'] in slow_host_prepared:
                        slow_host_waiting.append(snmp_task)
                        continue
                    else:
                        slow_host_prepared.append(snmp_task['host'])
                # Add task dispatcher
                self.append_task_to_dispatcher(snmp_task)

            if self.task_prepared > 0:
                # Launch SNMP requests
                self.cmdgen.snmpEngine.transportDispatcher.runDispatcher()
            else:
                # Sleep
                time.sleep(0.1)

        logger.info("[SnmpBooster] [code 0604] is stopped")

    def stop_worker(self):
        """ Stop SNMP worker thread """
        logger.info("[SnmpBooster] [code 0605] will be stopped")
        self.must_run = False


def handle_snmp_error(error_indication, cb_ctx, request_type):
    """ Handle SNMP errors """
    if error_indication is None:
        # No error
        return False

    # Get results
    results = cb_ctx[0]
    # Current elected service result
    service_result = cb_ctx[1]

    # Log SNMP error
    logger.error("[SnmpBooster] [code 0606] [%s] SNMP Error: "
                 "%s" % (service_result['host'],
                         str(error_indication)))
    # If is a get request
    if request_type == "get":
        # We set SNMP error in all oids
        for result in results.values():
            result['error'] = str(error_indication)

    return True


def callback_get(send_request_handle, error_indication, error_status,
                 error_index, var_binds, cb_ctx):
    """ Callback function for GET SNMP requests """
    # Get the oid list
    results = cb_ctx[0]

    # Current elected service result
    service_result = cb_ctx[1]
    # Get queue to submit result
    result_queue = cb_ctx[2]

    # Handle errors
    if handle_snmp_error(error_indication, cb_ctx, "get"):
        # set as received
        service_result['state'] = 'received'
        result_queue.put(results)
        return False

    # browse reponses
    for oid, value in var_binds:
        # for each oid, value
        # prepare the oid
        oid = "." + oid.prettyPrint()
        # if we need this oid
        if oid in results:
            # Check if we have a nosuchinstance error
            if value == noSuchInstance:
                # Log NoSuchInstance SNMP error
                message = "Oid not found on the device: %s" % oid
                logger.error("[SnmpBooster] [code 0607] [%s, %s] SNMP Error: "
                             "%s" % (results.values()[0]['key']['host'],
                                     results[oid]['key']['service'],
                                     message))
                results[oid]['error'] = message
            else:
                # save value
                results[oid]['value'] = value

            # save check time
            results[oid]['check_time'] = time.time()

    # Check if we get all values
    result_with_value_or_error = [oid['value'] for oid in results.values()
                                  if oid.get('value') is None
                                  and oid.get('error') is None]
    if len(result_with_value_or_error) == 0:
        # Add a saving task to the saving queue
        # (processed by the function save_results)
        result_queue.put(results)

        # Prepare datas for the current service
        tmp_results = [r for r in results.values()
                       if r['key']['host'] == service_result['host']
                       and r['key']['service'] == service_result['service']]
        for tmp_result in tmp_results:
            key = tmp_result.get('key')
            # ds name
            ds_names = key.get('ds_names')
            for ds_name in ds_names:
                # Last value
                last_value_key = ".".join(("ds",
                                           ds_name,
                                           key.get('oid_type') + "_value_last"
                                           )
                                          )
                # New value
                value_key = ".".join(("ds",
                                      ds_name,
                                      key.get('oid_type') + "_value"
                                      )
                                     )
                # Set last value
                service_result['db_data']['ds'][ds_name][last_value_key] = tmp_result.get('value_last')
                # Set value
                service_result['db_data']['ds'][ds_name][value_key] = tmp_result.get('value')
        # Set last check time
        service_result['db_data']['check_time_last'] = service_result['db_data'].get('check_time')
        # Set check time
        service_result['db_data']['check_time'] = time.time()
        # set as received
        service_result['state'] = 'received'
        # Calculate execution time
        service_result['execution_time'] = time.time() - service_result['start_time']

    else:
        pass
        # Not all data are received, we need to wait an other query


def callback_mapping_next(send_request_handle, error_indication,
                          error_status, error_index, var_binds, cb_ctx):
    """ Callback function for GENEXT SNMP requests """

    # Retrive context
    mapping_oid = cb_ctx[0]
    result = cb_ctx[2]

    # Handle errors
    if handle_snmp_error(error_indication, cb_ctx, "next"):
        result['finished'] = True
        return False

    # Parse snmp results
    for table_row in var_binds:
        for oid, instance_name in table_row:
            oid = "." + oid.prettyPrint()
            # Test if we are not in the mapping oid
            if not oid.startswith(mapping_oid):
                # We are not in the mapping oid
                result['finished'] = True
                return False
            instance = oid.replace(mapping_oid + ".", "")

            # DEBUGGING
            # print "OID", oid
            # print "MAPPING", mapping_oid
            # print "VAL", instance_name.prettyPrint()
            # END DEBUGGING

            # Handle illegal characters
            cleaned_instance_name = re.sub("[,:/ ]", "_", str(instance_name))
            # If we need this instance we store it
            if instance_name in result['data']:
                result['data'][instance_name] = instance
            # If we need this 'cleaned' instance we store it
            elif cleaned_instance_name in result['data']:
                result['data'][cleaned_instance_name] = instance

            # Check if mapping is finished
            if all(result['data'].values()):
                result['finished'] = True
                return False

    return True


def callback_mapping_bulk(send_request_handle, error_indication,
                          error_status, error_index, var_binds, cb_ctx):
    """ Callback function for BULK SNMP requests """

    # Retrive context
    mapping_oid = cb_ctx[0]
    result = cb_ctx[2]

    # Handle errors
    if handle_snmp_error(error_indication, cb_ctx, "bulk"):
        result['finished'] = True
        return False

    # Parse snmp results
    for table_row in var_binds:
        for oid, instance_name in table_row:
            oid = "." + oid.prettyPrint()
            # Test if we are not in the mapping oid
            if not oid.startswith(mapping_oid):
                # We are not in the mapping oid
                result['finished'] = True
                return False
            # Get instance
            instance = oid.replace(mapping_oid + ".", "")

            # DEBUGGING
            # print "OID", oid
            # print "MAPPING", mapping_oid
            # print "VAL", instance_name.prettyPrint()
            # END DEBUGGING

            # Handle illegal characters
            cleaned_instance_name = re.sub("[,:/ ]", "_", str(instance_name))
            # If we need this instance we store it
            if instance_name in result['data']:
                result['data'][instance_name] = instance
            # If we need this 'cleaned' instance we store it
            elif cleaned_instance_name in result['data']:
                result['data'][cleaned_instance_name] = instance

            # Check if mapping is finished
            if all(result['data'].values()):
                result['finished'] = True
                return False

    return True
