# encoding=utf-8

import utils
from config import *

VLAN_INTERFACE_DETAIL = ['vlan protocol 802.1q',
                         'vlan protocol 802.1Q',
                         'vlan id']


def _execute(options, command, args,
             namespace=None, ):
    opt_list = ['-%s' % o for o in options]
    if namespace:
        ip_cmd = ['ip', 'netns', 'exec', namespace, 'ip']
    else:
        ip_cmd = ['ip']
    return utils.execute(ip_cmd + opt_list + [command] + list(args), )


# this class is outside API
# name: a port's name
# namespace: a namespace name
class IPDevice(object):
    def __init__(self, name=None, namespace=None):
        self.namespace = namespace
        self.name = name
        self.link = IpLinkCommand(self.name, self.namespace)
        self.addr = IpAddrCommand(self.name, self.namespace)
        self.netns = IpNetnsCommand(self.name, self.namespace)
        self.route = IpRouteCommand(self.name, self.namespace)
        self.ipwrapper = IPWrapper(self.name, self.namespace)
        self.iprule = IpRule()

    def __eq__(self, other):
        return (other is not None and self.name == other.name
                and self.namespace == other.namespace)

    def __str__(self):
        return self.name


class IPWrapper(object):
    def __init__(self, name, namespace=None):
        self.name = name
        self.namespace = namespace
        self.netns = IpNetnsCommand(self.name, self.namespace)

    # get a namesapce ports
    def get_devices(self, exclude_loopback=False):
        retval = []
        output = _execute(['o', 'd'], 'link', ('list',), self.namespace)
        for line in output.split('\n'):
            if '<' not in line:
                continue
            tokens = line.split(' ', 2)
            if len(tokens) == 3:
                if any(v in tokens[2] for v in VLAN_INTERFACE_DETAIL):
                    delimiter = '@'
                else:
                    delimiter = ':'
                name = tokens[1].rpartition(delimiter)[0].strip()

                if exclude_loopback and name == LOOPBACK_DEVNAME:
                    continue

                retval.append(name)
        return retval

    # add tun device
    def add_tuntap(self, name, mode='tap'):
        _execute('', 'tuntap', ('add', name, 'mode', mode))

    # add veth peer
    def add_veth(self, name1, name2, namespace2=None):
        args = ['add', name1, 'type', 'veth', 'peer', 'name', name2]

        if namespace2 is None:
            namespace2 = self.namespace
        else:
            args += ['netns', namespace2]

        _execute('', 'link', tuple(args))

    # del veth peer. you can delete any one
    def del_veth(self, name):
        """Delete a virtual interface between two namespaces."""
        _execute('', 'link', ('del', name))

    # not use
    def namespace_is_empty(self):
        return not self.get_devices(exclude_loopback=True)

    # not use
    def garbage_collect_namespace(self):
        """Conditionally destroy the namespace if it is empty."""
        if self.namespace and self.netns.exists(self.namespace):
            if self.namespace_is_empty():
                self.netns.delete(self.namespace)
                return True
        return False

    # get all namespace name
    def get_namespaces(self):
        output = _execute('', 'netns', ('list',), namespace=self.namespace)
        return [l.strip() for l in output.split('\n')]


# IP rule. not use
class IpRule(object):
    def add_rule_from(self, ip, table, rule_pr):
        args = ['add', 'from', ip, 'lookup', table, 'priority', rule_pr]
        ip = _execute('', 'rule', tuple(args))
        return ip

    def delete_rule_priority(self, rule_pr):
        args = ['del', 'priority', rule_pr]
        ip = _execute('', 'rule', tuple(args))
        return ip


class IpLinkCommand(object):
    COMMAND = 'link set'

    # name : a port name
    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace

    # change a port status to up
    def set_port_up(self):
        _execute('', self.COMMAND, ('%s' % self.name, 'up'), self.namespace)

    # change a port status to down
    def set_port_down(self):
        _execute('', self.COMMAND, ('%s' % self.name, 'down'), self.namespace)

    # add a port to a namespace
    def set_netns(self):
        _execute('', self.COMMAND, ('%s' % self.name,
                                    'netns',
                                    '%s' % self.namespace,
                                    ))

    # delete a port
    def delete(self):
        _execute('', 'delete', self.name, self.namespace)


class IpAddrCommand(object):
    COMMAND = 'addr'

    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace

    # 给接口添加IP地址
    def add_ip(self, ip, mask):
        _execute('', self.COMMAND,
                 ('add',
                  '%s/%d' % (ip, mask),
                  'dev',
                  self.name),
                 self.namespace
                 )

    # 删除接口上的IP地址
    def delete_ip(self, ip, mask):
        _execute('', self.COMMAND,
                 ('del',
                  '%s/%d' % (ip, mask),
                  'dev',
                  self.name,),
                 self.namespace
                 )

    # flush the port (clean ip)
    def flush(self):
        _execute('', self.COMMAND + 'flush', self.name)


class IpRouteCommand(object):
    COMMAND = 'route'

    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace

    # add gateway
    def add_gateway(self, gateway, metric=None, table=None):
        args = ['replace', 'default', 'via', gateway]
        if metric:
            args += ['metric', metric]
        args += ['dev', self.name]
        if table:
            args += ['table', table]
        _execute('', self.COMMAND,
                 args, self.namespace)

    # delete gateway
    def delete_gateway(self, gateway=None, table=None):
        args = ['del', 'default']
        if gateway:
            args += ['via', gateway]
        args += ['dev', self.name]
        if table:
            args += ['table', table]
        _execute('', self.COMMAND,
                 args, self.namespace)

    # list all route
    def list_onlink_routes(self):
        def iterate_routes():
            output = _execute('', self.COMMAND, ('list', 'dev', self.name, 'scope', 'link'), self.namespace)
            for line in output.split('\n'):
                line = line.strip()
                if line and not line.count('src'):
                    yield line

        return [x for x in iterate_routes()]

    # add a route
    # cidr like 5.5.5.0/24
    def add_onlink_route(self, cidr):
        _execute('', self.COMMAND, ('replace', cidr, 'dev', self.name, 'scope', 'link'), self.namespace)

    # delete a route
    # cidr like 5.5.5.0/24
    def delete_onlink_route(self, cidr):
        _execute('', self.COMMAND, ('del', cidr, 'dev', self.name, 'scope', 'link'), self.namespace)

    # get the gateway ip address
    def get_gateway(self, scope=None, filters=None):
        if filters is None:
            filters = []

        retval = None

        if scope:
            filters += ['scope', scope]

        route_list_lines = _execute('', self.COMMAND, ('list', 'dev', self.name,), self.namespace).split('\n')
        default_route_line = next((x.strip() for x in
                                   route_list_lines if
                                   x.strip().startswith('default')), None)
        if default_route_line:
            gateway_index = 2
            parts = default_route_line.split()
            retval = dict(gateway=parts[gateway_index])
            if 'metric' in parts:
                metric_index = parts.index('metric') + 1
                retval.update(metric=int(parts[metric_index]))

        return retval

    # add a route
    # cidr: destination network like 5.5.5.0/24
    # ip: next hop ip address like 1.1.1.1
    # table : ip route table
    def add_route(self, cidr, ip, table=None):
        args = ['replace', cidr, 'via', ip, 'dev', self.name]
        if table:
            args += ['table', table]
        _execute('', self.COMMAND, args, self.namespace)

    def delete_route(self, cidr, ip, table=None):
        args = ['del', cidr, 'via', ip, 'dev', self.name]
        if table:
            args += ['table', table]
        _execute('', self.COMMAND, args, self.namespace)


class IpNetnsCommand(object):
    COMMAND = 'netns'

    def __init__(self, name, namespace):
        self.name = name
        self.namespace = namespace

    # 添加一个命名空间
    def add(self, name):
        _execute('', self.COMMAND, ('add', name))

    # 删除一个命名空间
    def delete(self, name):
        _execute('', self.COMMAND, ('delete %s' % name,))

    # 检查命名空间是否存在
    def exists(self, name):
        output = _execute('o', self.COMMAND, ('list',),)

        for line in output.split('\n'):
            if name == line.strip():
                return True
        return False
