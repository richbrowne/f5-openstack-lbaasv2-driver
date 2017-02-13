# coding=utf-8
u"""Service Module for F5® LBaaSv2."""
# Copyright 2014-2016 F5 Networks Inc.
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

import datetime
import uuid

from neutron.api.v2 import attributes
from neutron.common import constants as neutron_const
from neutron.extensions import portbindings

from oslo_log import helpers as log_helpers
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class F5NetworksNeutronClient(object):

    def __init__(self, plugin):
        self.plugin = plugin
        self.network_cache = {}
        self.subnet_cache = {}
        self.last_cache_update = datetime.datetime.fromtimestamp(0)

    def create_port_for_member(self,
                               context,
                               ip_address,
                               mac_address=None,
                               network_id=None, subnet_id=None):
        member_port = None

        if not mac_address:
            mac_address = attributes.ATTR_NOT_SPECIFIED

        with context.session.begin(subtransactions=True):
            member_port = self.create_port_on_subnet_with_specific_ip(
                context, subnet_id, ip_address=ip_address)
        return member_port

    def create_port_for_member(self,
                               context,
                               ip_address,
                               mac_address=None,
                               network_id=None, subnet_id=None):
        member_port = None

        if not mac_address:
            mac_address = attributes.ATTR_NOT_SPECIFIED

        with context.session.begin(subtransactions=True):
            member_port = self.create_port_on_subnet_with_specific_ip(
                context, subnet_id, ip_address=ip_address)
        return member_port

    @log_helpers.log_method_call
    def create_port_on_subnet(self, context, subnet_id=None,
                              mac_address=None,
                              name="", fixed_address_count=1, host=""):
        """Create port on subnet."""
        port = None

        if not mac_address:
            mac_address = attributes.ATTR_NOT_SPECIFIED

        with context.session.begin(subtransactions=True):
            if subnet_id:
                try:
                    subnet = self.plugin.db._core_plugin.get_subnet(
                        context,
                        subnet_id
                    )
                    fixed_ip = {'subnet_id': subnet['id']}
                    if fixed_address_count > 1:
                        fixed_ips = []
                        for _ in range(0, fixed_address_count):
                            fixed_ips.append(fixed_ip)
                    else:
                        fixed_ips = [fixed_ip]

                    port_data = {
                        'tenant_id': subnet['tenant_id'],
                        'name': name,
                        'network_id': subnet['network_id'],
                        'mac_address': mac_address,
                        'admin_state_up': True,
                        'device_id': "",
                        'device_owner': 'network:f5lbaasv2',
                        'status': neutron_const.PORT_STATUS_ACTIVE,
                        'fixed_ips': fixed_ips
                    }

                    if ('binding:capabilities' in
                            portbindings.EXTENDED_ATTRIBUTES_2_0['ports']):
                        port_data['binding:capabilities'] = {
                            'port_filter': False}
                    port = self.plugin.db._core_plugin.create_port(
                        context, {'port': port_data})

                    # Because ML2 marks ports DOWN by default on creation
                    update_data = {
                        'status': neutron_const.PORT_STATUS_ACTIVE
                    }
                    self.plugin.db._core_plugin.update_port(
                        context, port['id'], {'port': update_data})

                except Exception as e:
                    LOG.error("Exception: create_port_on_subnet: %s",
                              e.message)
            context.session.flush()
            return port

    @log_helpers.log_method_call
    def create_port_on_subnet_with_specific_ip(
            self, context, subnet_id=None,
            mac_address=None,
            ip_address=None, name="", host=""):
        """Create port on subnet with specific ip address."""
        if not mac_address:
            mac_address = attributes.ATTR_NOT_SPECIFIED

        if subnet_id and ip_address:
            subnet = self.plugin.db._core_plugin.get_subnet(
                context,
                subnet_id
            )
            fixed_ip = {
                'subnet_id': subnet['id'],
                'ip_address': ip_address
            }
            port_data = {
                'tenant_id': subnet['tenant_id'],
                'name': name,
                'network_id': subnet['network_id'],
                'mac_address': mac_address,
                'admin_state_up': True,
                'device_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, str(host))),
                'device_owner': 'network:f5lbaasv2',
                'status': neutron_const.PORT_STATUS_ACTIVE,
                'fixed_ips': [fixed_ip]
            }
            if ('binding:capabilities' in
                    portbindings.EXTENDED_ATTRIBUTES_2_0['ports']):
                port_data['binding:capabilities'] = {'port_filter': False}
            port = self.plugin.db._core_plugin.create_port(
                context, {'port': port_data})
            # Because ML2 marks ports DOWN by default on creation
            update_data = {
                'status': neutron_const.PORT_STATUS_ACTIVE
            }
            self.plugin.db._core_plugin.update_port(
                context, port['id'], {'port': update_data})

            context.session.flush()

            return port

    @log_helpers.log_method_call
    def get_port_by_name(self, context, port_name=None):
        """Get port by name."""
        if port_name:
            filters = {'name': [port_name]}
            return self.driver.plugin.db._core_plugin.get_ports(
                context,
                filters=filters
            )

    @log_helpers.log_method_call
    def delete_port(self, context, port_id=None, mac_address=None):
        """Delete port."""
        if port_id:
            self.driver.plugin.db._core_plugin.delete_port(context, port_id)
        elif mac_address:
            filters = {'mac_address': [mac_address]}
            ports = self.driver.plugin.db._core_plugin.get_ports(
                context,
                filters=filters
            )
            for port in ports:
                self.driver.plugin.db._core_plugin.delete_port(
                    context,
                    port['id']
                )

    @log_helpers.log_method_call
    def delete_port_by_name(self, context, port_name=None):
        """Delete port by name."""
        with context.session.begin(subtransactions=True):
            if port_name:
                filters = {'name': [port_name]}
                try:
                    ports = self.driver.plugin.db._core_plugin.get_ports(
                        context,
                        filters=filters
                    )
                    for port in ports:
                        self.driver.plugin.db._core_plugin.delete_port(
                            context,
                            port['id']
                        )
                except Exception as e:
                    LOG.error("failed to delete port: %s", e.message)

    @log_helpers.log_method_call
    def get_ports_for_fixedip(self, context, subnet_id=None,
                              ip_address=None):
        """Get ports for network."""
        ports = []
        with context.session.begin(subtransactions=True):
            try:
                filters = \
                    {'fixed_ips': {'subnet_id': subnet_id,'ip_address'=ip_address}}
                ports = self.driver.plugin.db._core_plugin.get_ports(
                    context,
                    filters=filters
                )
            except Exception as e:
                LOG.error("Exception: get_ports_for_fixedip: %s", e.message)

        return ports
