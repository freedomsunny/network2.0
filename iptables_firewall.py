# encoding=utf-8

import utils
from LogException import *
from iptables_manager import *
from ipset_manager import *

SG_CHAIN = 'sg-chain'
INGRESS_DIRECTION = 'ingress'
EGRESS_DIRECTION = 'egress'
DIRECTION_IP_PREFIX = {'ingress': 'source_ip_prefix',
                       'egress': 'dest_ip_prefix'}
IPSET_DIRECTION = {INGRESS_DIRECTION: 'src',
                   EGRESS_DIRECTION: 'dst'}
VM_INTERFACE_PREFIX = 'tap'


class IptablesFirewallDriver(object):
    IPTABLES_DIRECTION = {INGRESS_DIRECTION: 'physdev-out',
                          EGRESS_DIRECTION: 'physdev-in'}

    def __init__(self, chain_uid=None, namespace=None,
                 table=None, wrap=True):

        self.namespace = namespace
        self.wrap = wrap
        self.chain_uid = chain_uid
        self.table = table
        self.uid_prefix = str(chain_uid).strip()[:UID_PREFIX_BIT]
        self.port_name = VM_INTERFACE_PREFIX + self.uid_prefix
        self.ipset_manager = IpsetManager(self.chain_uid, self.namespace)
        self.ipset_name = get_ipset_chain_name(self.chain_uid)
        self.chain_suffix = {INGRESS_DIRECTION: 'i%s' % self.uid_prefix,
                             EGRESS_DIRECTION: 'o%s' % self.uid_prefix,
                             }

    def wrap_builtin_chains(self):
        iptables = IptablesManager()
        builtin_chains = {4: {'filter': ['INPUT', 'OUTPUT', 'FORWARD'],
                              'nat': ['PREROUTING', 'OUTPUT', 'POSTROUTING']},
                          }
        ipv4 = iptables.ipv4

        for table, chains in builtin_chains[IP_VERSION].iteritems():
            for chain in chains:
                # Wrap built-in chain name
                wrap_chain = iptables.wrap_name + '-' + chain.strip()
                # first add chain
                ipv4[table].chains.add(wrap_chain)
                # so add rule to chain
                iptables.add_rule('-j $%s' % chain, table, chain_str=chain,
                                  rule_list=ipv4[table].rules, defer_apply=True)
            iptables.iptables_apply(table, obj=ipv4[table])

    # 只调用一次，调用时table参数必传
    def add_sg_chain(self):
        iptables = IptablesManager(SG_CHAIN, self.table)
        iptables.add_chain()

    # add ingress/egress chains
    def add_port_chain(self):
        # add chain about vm port
        for direction in sorted(DIRECTION_IP_PREFIX):
            chain_name_str = self.chain_suffix[direction]
            iptables = IptablesManager(chain_name_str, self.table)
            iptables.add_chain()

            # add rule to wrap chain
            self._add_chain_rule(direction)

    # remove port chain
    def remove_port_chain(self):
        # remove chain about vm port
        for direction in sorted(DIRECTION_IP_PREFIX):
            chain_name = self.chain_suffix[direction]
            self.delete_chain(chain_name)

    # direction = str
    # direction: ingress/egress
    # 实例化IptablesFirewallDriver类时时chain_name='FORWARD'/INPUT/OUTPUT
    def _add_chain_rule(self, direction):
        iptables = IptablesManager(chain_uid='FORWARD', table=self.table)
        device = self.port_name
        jump_rule = '-m physdev --%s %s --physdev-is-bridged ' \
                    '-j $%s' % (self.IPTABLES_DIRECTION[direction],
                                device,
                                SG_CHAIN)
        iptables.add_rule(jump_rule, self.table)
        # jump to the chain based on the device
        iptables = IptablesManager(SG_CHAIN, self.table)
        jump_rule = '-m physdev --%s %s --physdev-is-bridged ' \
                    '-j $%s' % (self.IPTABLES_DIRECTION[direction],
                                device,
                                self.chain_suffix[direction])
        iptables.add_rule(jump_rule, self.table)

    # ips = list
    # action = ACCEPT/DROP/REJECT str
    # direction: ingress/egress  (str)
    def init_ipset_rule(self, action, direction):
        chain_name = self.chain_suffix[direction]
        iptables = IptablesManager(chain_uid=chain_name, table=self.table,
                                   namespace=self.namespace, wrap=True)
        direction = IPSET_DIRECTION[direction]
        self.ipset_manager.create_ipset_chain(self.ipset_name)
        args = ['-m set',
                '--match-set',
                '%s' % self.ipset_name,
                direction,
                '-j %s' % action
                ]
        rule = ' '.join(args)
        iptables.add_rule(rule, self.table, self.chain_uid)

    # ips: a list
    def add_ipset_rule(self, ips):
        ipset_manager = self.ipset_manager
        if ips:
            for ip in ips:
                ipset_manager.add_member_to_ipset_chain(ip, self.ipset_name)

    # ips: a list
    def delete_ipset_rule(self, ips):
        ipset_manager = self.ipset_manager
        if ips:
            for ip in ips:
                ipset_manager.del_ipset_chain_member(self.ipset_name, ip)

    # direction = 'ingress'/'egress'
    def add_iptables_rule(self, rule, direction, wrap=True):
        chain_name = self.chain_suffix[direction]
        iptables = IptablesManager(chain_name, self.table, self.namespace, wrap=wrap)
        iptables.add_rule(rule, self.table, self.chain_uid)

    # direction = 'ingress'/'egress'
    def delete_rule(self, rule, direction, wrap=True):
        chain_name = self.chain_suffix[direction]
        iptables = IptablesManager(chain_name, self.table, self.namespace, wrap=wrap)
        iptables.remove_rule(rule)

    def delete_chain(self, chain_name, wrap=True):
        iptables = IptablesManager(chain_name, self.table, self.namespace, wrap=wrap)
        iptables.remove_chain()
