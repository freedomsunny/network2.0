# encoding=utf-8

import utils
from LogException import *
from config import *


def get_ipset_chain_name(uid):
    if uid:
        return IP_SET_PREFIX_NAME + uid[:UID_PREFIX_BIT]


class IpsetManager(object):
    """Wrapper for ipset."""

    def __init__(self, name=None, namespace=None):
        self.name = name
        self.namespace = namespace

    # 命令执行方法
    def _apply(self, cmd,):

        if self.namespace:
            cmd.insert(0, 'ip netns exec {}'.format(self.namespace))
        utils.execute(cmd)

    # 创建一个ipset列表
    def create_ipset_chain(self, name):
        cmd = [
            'ipset',
            'create',
            '-exist',
            name,
            'hash:net',
            ]
        self._apply(cmd)

    # 删除ipset
    def destroy_ipset_chain_by_name(self, name):
        self._destroy_ipset_chain(name)

    # 添加一个IP到ipset中
    def add_member_to_ipset_chain(self, member_ip, name):
        cmd = [
            'ipset',
            '-A',
            name,
            member_ip
        ]
        self._apply(cmd)

    # 清空ipset中的所有IP
    def flush_ipset_china(self, name):
        cmd = [
            'ipset',
            '-F',
            name
        ]
        self._apply(cmd)

    # 删除ipset中的一个元素
    def del_ipset_chain_member(self, chain_name, member_ip):
        cmd = ['ipset', 'del', chain_name, member_ip]
        self._apply(cmd)

    # ips ['1.1.1.1','1.1.1.2','2.2.2.1'....]
    def add_ip_members(self, ips, name):
        if ips:
            for ip in ips:
                self.add_member_to_ipset_chain(ip, name)
            return True
        else:
            msg = "ipset: no one or more ip can be add. check the ips"
            LogExceptionHelp.logException(msg)
            print(msg)

    # 重置IPset
    def _restore_ipset_chains(self):
        cmd = ['ipset', 'restore', '-exist']
        self._apply(cmd)

    def _swap_ipset_chains(self, src_chain, dest_chain):
        cmd = ['ipset', 'swap', src_chain, dest_chain]
        self._apply(cmd)

    # 删除一个ipset
    def _destroy_ipset_chain(self, chain_name):
        cmd = ['ipset', 'destroy', chain_name]
        self._apply(cmd)
