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
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.


"""
This module contains the SnmpBoosterArbiter class which is the part
of SNMP Booster loaded in the Arbiter
"""

import logging

from alignak.basemodule import BaseModule
from alignak.util import to_int

#from libs.dbclient import DBClient
from libs.redisclient import DBClient

logger = logging.getLogger('alignak.module')  # pylint: disable=C0103


class SnmpBooster(BaseModule):
    """ SNMP booster base module class
        Improve SNMP checks
    """
    def __init__(self, mod_conf):
        BaseModule.__init__(self, mod_conf)
        self.version = "2.0.0"
        self.datasource_file = getattr(mod_conf, 'datasource', None)
        self.db_host = getattr(mod_conf, 'db_host', "127.0.0.1")
        self.db_port = to_int(getattr(mod_conf, 'db_port', 6379))
        self.db_name = getattr(mod_conf, 'db_name', 'booster_snmp')
        self.loaded_by = getattr(mod_conf, 'loaded_by', None)
        self.datasource = None
        self.db_client = None
        self.i_am_dying = False

    def init(self):
        """
        Called by poller to say 'let's prepare yourself guy'

        :return: True to inform ModuleManager of a correct initialization
        """
        logger.info("[SnmpBooster] [code 1101] Initialization of "
                    "the SNMP Booster %s" % self.version)
        self.i_am_dying = False

        if self.datasource_file is None and self.loaded_by == 'arbiter':
            # Kill snmp booster if config_file is not set
            logger.error("[SnmpBooster] [code 1102] Please set "
                         "datasource parameter")
            self.i_am_dying = True
            return False

        # Prepare database connection
        if self.loaded_by in ['arbiter', 'poller']:
            self.db_client = DBClient(self.db_host, self.db_port, self.db_name)
            # Connecting
            if not self.db_client.connect():
                self.i_am_dying = True
                return False

        return True
