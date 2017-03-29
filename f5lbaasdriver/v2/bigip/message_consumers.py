#!/usr/bin/env python
# Copyright 2017 F5 Networks Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os

import oslo_config
import oslo_messaging as messaging

from neutron.common import rpc as neutron_rpc
from neutron.db import agents_db

from oslo_log import log as logging
from oslo_service import service

from f5lbaasdriver.v2.bigip import constants_v2 as constants

LOG = logging.getLogger(__name__)


class F5RPCConsumer(service.Service):
    """Creates a RPC Consumer that will Return and Use the Driver For Calls

    This is a standard, RPC service based upon the provided driver.
    This should be executed through its creation and use of standard
    oslo_service.Service actions.
    """
    def __init__(self, driver, **kargs):
        super(F5RPCConsumer, self).__init__(**kargs)
        self.topic = constants.TOPIC_PROCESS_ON_HOST_V2
        self.driver = driver
        if self.driver.env:
            self.topic = self.topic + "_" + self.driver.env

        server = oslo_config.cfg.CONF.host
        self.transport = messaging.get_transport(
            oslo_config.cfg.CONF)
        self.target = messaging.Target(topic=self.topic, server=server,
                                       exchange="common", fanout=False)
        self.plugin_rpc = driver.plugin_rpc
        self.endpoints = [self.plugin_rpc,
                          agents_db.AgentExtRpcCallback(driver.plugin.db)]

        self.connection = neutron_rpc.create_connection(new=True)
        self.consumer = self.connection.create_consumer(
            self.topic, self.endpoints, fanout=False)

        self.server = None
        LOG.debug("Created F5RPCConsumer (Driver: {}, PID: {})".format(
            driver, os.getpid()))

    def start(self):
        """Starts the oslo_messaging Listener"""
        super(F5RPCConsumer, self).start()
        msg = str("Started threaded F5RPCConsumer Service "
                  "(Driver: {}, PID: {}, topic: {})").format(self.driver,
                                                             os.getpid(),
                                                             self.topic)
        # self.server = messaging.get_rpc_server(self.transport, self.target,
        #                                       self.endpoints,
        #                                       executor='eventlet')
        # self.server.start()
        self.connection.consume_in_threads()
        LOG.debug(msg)

    def stop(self, graceful=False):
        if self.server:
            LOG.info("Stopping consumer... (Driver: {}, PID: {})".format(
                self.driver, os.getpid()))
            self.server.stop()
            if graceful:
                LOG.info("Consumer stop executing... gracefully waiting")
                self.server.wait()
        if self.connection:
            self.connection.close()
        super(F5RPCConsumer, self).stop(graceful=graceful)

    def reset(self):
        if self.server:
            self.server.reset()
        super(F5RPCConsumer, self).reset()
