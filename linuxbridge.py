#!/usr/bin/env python

import utils
from LogException import *
from config import *


# NOTE(toabctl): Don't use /sys/devices/virtual/net here because not all tap
# devices are listed here (i.e. when using Xen)
BRIDGE_FS = "/sys/class/net/"

# brname: a linux bridge name


class LinuxBridgeManager(object):
    def __init__(self, brname):
        self.name = brname

    def create_br(self):
        cmd = [
            'brctl',
            'addbr',
            self.name,
        ]
        utils.execute(cmd)

    def remove_br(self):
        cmd = [
            'brctl',
            'delbr',
            self.name,
        ]
        utils.execute(cmd)

    # note: the port must be exist
    def add_port(self, port):
        cmd = [
            'brctl',
            'addif',
            self.name,
            port
        ]
        utils.execute(cmd)

    # note: the port must be exist
    def remove_port(self, port):
        cmd = [
            'brctl',
            'delif',
            self.name,
            port
        ]
        utils.execute(cmd)

    def interface_exists_on_bridge(self, bridge, interface):
        directory = '/sys/class/net/%s/brif' % bridge
        for filename in os.listdir(directory):
            if filename == interface:
                return True
        return False

    def get_all_bridges(self):
        neutron_bridge_list = []
        bridge_list = os.listdir(BRIDGE_FS)
        for bridge in bridge_list:
            if bridge.startswith(BRIDGE_NAME_PREFIX):
                neutron_bridge_list.append(bridge)
        return neutron_bridge_list
