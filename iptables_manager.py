# encoding=utf-8

import os
import inspect
import utils
from LogException import *
from config import *


# NOTE(vish): Iptables supports chain names of up to 28 characters,  and we
#             add up to 12 characters to binary_name which is used as a prefix,
#             so we limit it to 16 characters.
#             (max_chain_name_length - len('-POSTROUTING') == 16)
def get_binary_name():
    """Grab the name of the binary we're running in."""
    return os.path.basename(inspect.stack()[-1][1])[:16]


binary_name = get_binary_name()

# A length of a chain name must be less than or equal to 11 characters.
# <max length of iptables chain name> - (<binary_name> + '-') = 28-(16+1) = 11
MAX_CHAIN_LEN_WRAP = 11
MAX_CHAIN_LEN_NOWRAP = 28

# Number of iptables rules to print before and after a rule that causes a
# a failure during iptables-restore
IPTABLES_ERROR_LINES_OF_CONTEXT = 5
IP_VERSION = 4


def get_chain_name(chain_name, wrap=True):
    if wrap:
        return chain_name[:MAX_CHAIN_LEN_WRAP]
    else:
        return chain_name[:MAX_CHAIN_LEN_NOWRAP]


class IptablesRule(object):
    def __init__(self, chain, rule, wrap=True):
        self.chain = chain
        self.rule = rule
        self.wrap = wrap

    def __eq__(self, other):
        return ((self.chain == other.chain) and
                (self.rule == other.rule) and
                (self.wrap == other.wrap))

    def __ne__(self, other):
        return not self == other

    def __str__(self):
        return '-A %s %s' % (self.chain, self.rule)


class IptablesTable(object):
    """An iptables table."""

    def __init__(self):
        self.rules = []
        self.remove_rules = []
        self.chains = set()
        self.remove_chains = set()


class IptablesManager(object):
    def __init__(self, chain_name=None, table=None, namespace=None,
                 suffix=None, wrap=True, state_less=False):
        self.execute = utils.exec_cmd
        self.chain_name = chain_name
        self.namespace = namespace
        self.suffix = suffix if not suffix else str(suffix).strip()
        self.wrap = wrap
        self.state_less = state_less
        self.table = table
        self.wrap_name = binary_name[:16]
        self.ipv4 = {'filter': IptablesTable(),
                     'nat': IptablesTable(),
                     }
        if table:
            self.chains = self.ipv4[table].chains
            self.remove_chains = self.ipv4[table].remove_chains
            self.rules = self.ipv4[table].rules
            self.remove_rules = self.ipv4[table].remove_rules

    def _get_chain_name(self):
        chain_name = get_chain_name(self.chain_name)
        if self.wrap and self.suffix:
            return self.wrap_name + '-' + self.suffix
        elif self.wrap:
            return self.wrap_name + '-' + chain_name

    def add_chain(self):
        name = self._get_chain_name()
        if len(name.strip()) > MAX_CHAIN_LEN_NOWRAP:
            raise ValueError('chain name can not greater than {} chars'.format(MAX_CHAIN_LEN_NOWRAP))
        self.chains.add(name)
        self.iptables_apply(self.table)

    def remove_chain(self):
        name = self._get_chain_name()
        self.remove_chains.add(name)
        self.iptables_apply(self.table)

    # defer_apply 是否延迟应用规则
    def add_rule(self, rule, table=None, chain_str=None, rule_list=None, wrap=True, defer_apply=False):
        chain_name = (self._get_chain_name() if self.chain_name else chain_str)
        if '$' in rule:
            rule = ' '.join(
                self._wrap_target_chain(e, wrap) for e in rule.split(' '))

        (rule_list if not self.table else self.rules).append(IptablesRule(chain_name, rule, wrap))
        if not defer_apply:
            self.iptables_apply(table)

    def remove_rule(self, rule):
        self.remove_rules.append(rule)
        self.iptables_apply(self.table)

    def _wrap_target_chain(self, s, wrap):
        if s.startswith('$'):
            s = ('%s-%s' % (self.wrap_name, get_chain_name(s[1:], wrap)))

        return s

    # 应用规则
    def iptables_apply(self, table=None, obj=None):
        table = (table if table else self.table)
        s = [('iptables', table)]
        for cmd, table in s:
            args = ['%s-save' % (cmd,), '-c']
            if self.namespace:
                args = ['ip', 'netns', 'exec', self.namespace] + args
            all_tables = utils.execute(args)[1]
            all_lines = all_tables.split('\n')
            start, end = self._find_table(all_lines, table)
            all_lines[start:end] = self._modify_rules(
                all_lines[start:end], obj)

            args = ['%s-restore' % (cmd,), '-c']
            if self.namespace:
                args = ['ip', 'netns', 'exec', self.namespace] + args
            try:
                self.execute(args, process_input='\n'.join(all_lines),
                             )
                print("IPTablesManager.apply completed with success")
            except Exception as e:
                print(e)
                LogExceptionHelp.logException(u"IPTablesManager.apply error. msg: {}".format(e))

    def _find_table(self, lines, table_name):
        try:
            start = lines.index('*%s' % table_name) - 1
        except ValueError:
            print('Unable to find table %s' % table_name)
            LogExceptionHelp.logException('Unable to find table %s' % table_name)
            return (0, 0)
        end = lines[start:].index('COMMIT') + start + 2
        return (start, end)

    # 找到规则从哪一行开始
    def _find_rules_index(self, lines):
        seen_chains = False
        rules_index = 0
        for rules_index, rule in enumerate(lines):
            if not seen_chains:
                if rule.startswith(':'):
                    seen_chains = True
            else:
                if not rule.startswith(':'):
                    break

        if not seen_chains:
            rules_index = 2

        return rules_index

    def _find_last_entry(self, filter_list, match_str):
        for s in reversed(filter_list):
            s = s.strip()
            if match_str in s:
                return s

    def _get_all_rules(self, current_lines, chain_str, ):
        rules_index = self._find_rules_index(current_lines)
        rules = [s for s in current_lines[rules_index:-1] if chain_str in s]
        for rule in rules:
            self.rules.append(IptablesRule(chain_str, rule, ))

    def get_chain_rules(self, chain, current_lines):
        chain = str(chain).strip()
        chain_rules = [line for line in current_lines if line.startswith('[') and chain in line.strip()]
        return chain_rules

    def clean_chain_rules(self, chain, current_lines):
        chain = str(chain).strip()
        current_lines = [s for s in current_lines if chain not in s.strip() and s.startswith('[')]
        return current_lines

    def _modify_rules(self, current_lines, obj=None):
        chains = sorted((self.chains if self.table else obj.chains))
        remove_chains = (self.remove_chains if self.table else obj.remove_chains)
        rules = (self.rules if self.table else obj.rules)
        remove_rules = (self.remove_rules if self.table else obj.remove_chains)
        new_filter = current_lines

        if chains:
            our_chains = []
            for chain in chains:
                chain_str = str(chain).strip()
                dup = self._find_last_entry(new_filter, chain_str)

                if not dup:
                    # add-on the [packet:bytes]
                    chain_str = ':' + chain_str + ' - [0:0]'
                else:
                    LogExceptionHelp.logException("chain {} is already exist".format(chain))
                    continue

                our_chains += [chain_str]
            rules_index = self._find_rules_index(new_filter)
            new_filter[rules_index:rules_index] = our_chains

        if rules:
            our_rules = []
            for rule in rules:
                rule_str = str(rule).strip()
                dup = [s for s in new_filter if rule_str in s.strip()]
                if not dup:
                    rule_str = '[0:0] ' + rule_str
                else:
                    LogExceptionHelp.logException("rule {} is already exist".format(rule))
                our_rules += [rule_str]
            rules_index = self._find_rules_index(new_filter)
            new_filter[rules_index:rules_index] = our_rules

        if remove_chains:
            for remove_chain in remove_chains:
                remove_chain = str(remove_chain).strip()
                new_filter = [s for s in new_filter if remove_chain not in s.strip()]

        if remove_rules:
            for remove_rule in remove_rules:
                remove_rule = str(remove_rule).strip()
                new_filter = [s for s in new_filter if remove_rule not in s.strip()]

        return new_filter
