# -*- coding: utf-8 -*-

from linuxbridge import *
from ovs_lib import *
from dhcp import *
from ip_lib import *
from iptables_firewall import *
from config import *
from ipset_manager import *


# 每个虚拟机的接口需要调用一次
# port_uid为虚拟机每个接口的UUID
def create_vm_port_about(port_uid, vm_vlan, use_sg=True, table='filter'):
    vm_port_name = VM_PORT_PREFIX + port_uid[:UID_PREFIX_BIT]
    linux_bridge_name = BRIDGE_NAME_PREFIX + port_uid[:UID_PREFIX_BIT]
    linux_bridge_port_name = VM_BRIDGE_PORT_PREFIX + port_uid[:UID_PREFIX_BIT]
    ovs_bridge_port_name = VM_OVS_PORT_PREFIX + port_uid[:UID_PREFIX_BIT]
    ipset_chain_name = get_ipset_chain_name(port_uid)

    linux_bridge_obj = LinuxBridgeManager(linux_bridge_name)
    ip_tool_obj = IPDevice(linux_bridge_name)
    ovs_obj = BaseOVS(VM_bridge_Name)
    iptables_obj = IptablesFirewallDriver(port_uid, table=table)
    ipset_obj = IpsetManager()

    # if use Security Group, need create linux bridge and init iptables rule
    if use_sg:
        # create linux bridge
        linux_bridge_obj.create_br()
        # create linux path peer
        ip_tool_obj.ipwrapper.add_veth(linux_bridge_port_name, ovs_bridge_port_name)
        # add the vm and linux path peer port to the linux bridge
        linux_bridge_obj.add_port(linux_bridge_port_name)
        # add the port to the ovs and set tag
        ovs_obj.add_port(ovs_bridge_port_name)
        ovs_obj.set_port_tag(vm_vlan, ovs_bridge_port_name)

        # up the ports
        ip_tool_obj.link.set_port_up(linux_bridge_name)
        ip_tool_obj.link.set_port_up(linux_bridge_port_name)
        ip_tool_obj.link.set_port_up(ovs_bridge_port_name)

        # init Security Group policy
        iptables_obj.add_port_chain()
        ipset_obj.create_ipset_chain(ipset_chain_name)
    else:
        # if not use Security Group, we just add vm port to ovs bridge
        ovs_obj.add_port(vm_port_name)
        ip_tool_obj.link.set_port_up(vm_port_name)


# 启动虚拟机DHCP，一个网络启一个DHCP进程
# first是否是第一次调用，第一次启动会启动进程，第二次调用只会增加IP和MAC的绑定关系
def create_vm_dhcp(net_uid, ip, mask, mac, vlan=None, namespace=None, first=True):
    dhcp_ns_name = (namespace if namespace else NS_DHCP_PREFIX + net_uid[:UID_PREFIX_BIT])
    dhcp_ns_port_name = NS_DHCP_INTERFACE_PREFIX + net_uid[:UID_PREFIX_BIT]

    ip_about = ip_expr(ip, mask)
    ip_tool_obj = IPDevice(name=dhcp_ns_port_name, namespace=dhcp_ns_name)
    ovs_obj = BaseOVS(VM_bridge_Name)
    dhcp_obj = Dnsmasq_base(ip, mask, mac, net_uid, dhcp_ns_name)

    # if the first spawn dhcp process , need spawn dhcp process, and add ip to port
    if first:
        # create a namespace
        ip_tool_obj.netns.add(dhcp_ns_name)
        # add a ovs internal and set vlan tag
        ovs_obj.add_port_internal(dhcp_ns_port_name, vlan)

        if dhcp_ns_name:
            # add the port to namespace
            ip_tool_obj.link.set_netns(dhcp_ns_port_name)
        # link up port
        ip_tool_obj.link.set_port_up(dhcp_ns_port_name)
        # set dhcp listen port ip address and spawn dhcp process
        ip_tool_obj.addr.add_ip(dhcp_ns_port_name, ip_about.dhcp_listen_addr, mask)
        dhcp_obj.spawn_process()
    # if not the first spawn dhcp process , add vm's ip and mac to hosts file and reload process
    else:
        dhcp_obj.write_host_info(ip, mac)
        dhcp_obj.reload_process()


# 添加L3，三层路由.三层路由一个隔离空间一个
def create_l3(stu_ip, stu_mask, vm_ip, vm_mask, l3_uid, net_uid, vm_vlan, l3_vlan):
    l3_ns_name = L3_NAMESPACE_PREFIX + l3_uid[:UID_PREFIX_BIT]
    l3_vm_port_name = L3_VM_PORT_PREFIX + net_uid[:UID_PREFIX_BIT]
    l3_stu_port_name = L3_STU_PORT_PREFIX + l3_uid[:UID_PREFIX_BIT]

    vm_ip_about = ip_expr(vm_ip, vm_mask)
    user_ip_about = ip_expr(stu_ip, stu_mask)
    ovs_obj = BaseOVS(VM_bridge_Name)
    ip_tool_obj = IPDevice(namespace=l3_ns_name)

    # create a l3 namespace
    ip_tool_obj.netns.add(l3_ns_name)
    # ovs add internal ports for vm
    ovs_obj.add_port_internal(l3_vm_port_name, vm_vlan)
    # ovs add internal ports for student
    ovs_obj.add_port_internal(l3_stu_port_name, l3_vlan)
    # add the port to namespace
    ip_tool_obj.link.set_netns(l3_vm_port_name)
    ip_tool_obj.link.set_netns(l3_stu_port_name)
    # link up the port
    ip_tool_obj.link.set_port_up(l3_vm_port_name)
    ip_tool_obj.link.set_port_up(l3_stu_port_name)
    # set port's ip address
    ip_tool_obj.addr.add_ip(l3_vm_port_name, vm_ip_about.gateway, vm_mask)
    ip_tool_obj.addr.add_ip(l3_stu_port_name, user_ip_about.gateway, stu_mask)


# 添加路由条目
# cidr like 5.5.5.0/24
# out_port: dst network out put port
def add_route(l3_uid, cidr, out_port, namespace=None):
    l3_ns_name = (namespace if namespace else (L3_NAMESPACE_PREFIX + l3_uid[:UID_PREFIX_BIT]))

    ip_tool_obj = IPDevice(namespace=l3_ns_name)
    ip_tool_obj.route.add_onlink_route(cidr, out_port)


# 删除一条路由
# cidr like 5.5.5.0/24
# out_port: dst network out put port
def delete_route(l3_uid, cidr, out_port, namespace=None):
    l3_ns_name = (namespace if namespace else (L3_NAMESPACE_PREFIX + l3_uid[:UID_PREFIX_BIT]))

    ip_tool_obj = IPDevice(namespace=l3_ns_name)
    ip_tool_obj.route.delete_onlink_route(cidr, out_port)


# 添加流策略，用于学生登录
def user_login(**kwargs):
    ovs_obj = BaseOVS(Mirror_bridge)
    ovs_obj.add_flow(**kwargs)


# 删除流策略，用于学生退出
def user_logout(**kwargs):
    ovs_obj = BaseOVS(Mirror_bridge)
    ovs_obj.delete_flows(**kwargs)


# 清除虚拟机相关
def clean_vm_port_about(port_uid, use_sg=True, table='filter'):
    linux_bridge_name = BRIDGE_NAME_PREFIX + port_uid[:UID_PREFIX_BIT]
    linux_bridge_port_name = VM_BRIDGE_PORT_PREFIX + port_uid[:UID_PREFIX_BIT]
    ovs_bridge_port_name = VM_OVS_PORT_PREFIX + port_uid[:UID_PREFIX_BIT]
    ipset_chain_name = get_ipset_chain_name(port_uid)

    # objects
    linux_bridge_obj = LinuxBridgeManager(linux_bridge_name)
    ip_tool_obj = IPDevice(linux_bridge_name)
    ovs_obj = BaseOVS(VM_bridge_Name)
    iptables_obj = IptablesFirewallDriver(port_uid, table=table)
    ipset_obj = IpsetManager()

    # if use Security Group remove them
    if use_sg:
        # link down linux bridge port
        ip_tool_obj.link.set_port_down()
        # so remove linux bridge
        linux_bridge_obj.remove_br()
        # delete peer path.
        ip_tool_obj.ipwrapper.del_veth(linux_bridge_port_name)
        ovs_obj.delete_port(ovs_bridge_port_name)
        # remove Security Group about
        iptables_obj.remove_port_chain()
        # remove ipset chain
        ipset_obj.destroy_ipset_chain_by_name(ipset_chain_name)
    else:
        # if not use Security Group just remove ovs bridge's port and peer path port
        ip_tool_obj.ipwrapper.del_veth(linux_bridge_port_name)
        ovs_obj.delete_port(ovs_bridge_port_name)


# 清除DHCP相关
def clean_dhcp_about(net_uid, namespace=None):
    dhcp_ns_name = (namespace if namespace else NS_DHCP_PREFIX + net_uid[:UID_PREFIX_BIT])
    dhcp_ns_port_name = NS_DHCP_INTERFACE_PREFIX + net_uid[:UID_PREFIX_BIT]
    ovs_obj = BaseOVS(VM_bridge_Name)
    ip_tool_obj = IPDevice()
    dhcp_obj = Dnsmasq_base(net_uid=net_uid)

    # remove ovs bridge's port
    ovs_obj.delete_port(dhcp_ns_port_name)
    # remove namespace
    ip_tool_obj.netns.delete(dhcp_ns_name)
    # remove dhcp process and dhcp file
    dhcp_obj.kill_process()
    dhcp_obj.remove_vm_dhcp_file()


# 清除L3相关
def clean_l3_about(l3_uid, net_uid, namespace=None):
    l3_ns_name = (namespace if namespace else L3_NAMESPACE_PREFIX + l3_uid[:UID_PREFIX_BIT])
    l3_vm_port_name = L3_VM_PORT_PREFIX + net_uid[:UID_PREFIX_BIT]
    l3_stu_port_name = L3_STU_PORT_PREFIX + l3_uid[:UID_PREFIX_BIT]
    ovs_obj = BaseOVS(VM_bridge_Name)
    ip_tool_obj = IPDevice()

    # remove ovs bridge's port
    ovs_obj.delete_port(l3_vm_port_name)
    ovs_obj.delete_port(l3_stu_port_name)
    # remove namespace
    ip_tool_obj.netns.delete(l3_ns_name)


# 添加数据镜像
def data_mirror(vlan=Mirror_vlan):
    ovs_obj = BaseOVS(Mirror_bridge)
    ovs_obj.data_mirror(vlan)


# 清除bridge镜像
def clean_data_mirror():
    ovs_obj = BaseOVS(Mirror_bridge)
    ovs_obj.remove_data_mirror()


# 检查桥是否已经开启了数据镜像
def check_data_mirror(bridge=Mirror_bridge):
    ovs_obj = BaseOVS(bridge)
    return ovs_obj.is_exsit_mirror()


# 为虚拟机的接口添加ipset的防火墙规则
def add_ipset_rule(port_uid, action, direction, ips=None, table='filter'):
    iptables_obj = IptablesFirewallDriver(port_uid, table=table)

    # init ipset .init_ipset_rule(action, direction)
    if ips:
        iptables_obj.add_ipset_rule(ips)


def add_ip_to_ipset(port_uid, ips, table='filter'):
    iptables_obj = IptablesFirewallDriver(port_uid, table=table)

    iptables_obj.add_ipset_rule(ips)


# 为虚拟机接口增加防火墙规则
def add_rule(port_uid, rule, direction, wrap=True, table='filter'):
    iptables_obj = IptablesFirewallDriver(port_uid, table=table)
    iptables_obj.add_iptables_rule(rule, direction, wrap=wrap)


# 删除虚拟机接口防火墙规则
def remove_rule(port_uid, rule, direction, wrap=True,  table='filter'):
    iptables_obj = IptablesFirewallDriver(port_uid, table=table)
    iptables_obj.delete_rule(rule, direction, wrap=wrap)
