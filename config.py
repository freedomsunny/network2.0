# public
log_path = '/var/log/network/'
VM_bridge_Name = 'br0'
Mirror_bridge = 'br1'
Mirror_vlan = 4093
UID_PREFIX_BIT = 10
VM_PORT_PREFIX = 'tap'
USER_VLAN = 10
# ip_lib.py
L3_NAMESPACE_PREFIX = 'l3_ns-'
LOOPBACK_DEVNAME = 'lo'
L3_VM_PORT_PREFIX = 'l3-vm'
L3_STU_PORT_PREFIX = 'l3-st'
VM_BRIDGE_PORT_PREFIX = 'qvb-'
VM_OVS_PORT_PREFIX = 'qvo-'
# ovs_lib.py
ovs_vsctl_timeout = 10
# dhcp.py
NS_DHCP_PREFIX = 'qdhcp-'
NS_DHCP_INTERFACE_PREFIX = 'dhcp'
DHCP_CONFIG_FILE_PREFIX = '/var/lib/dnsmasq/dhcp/'
DHCP_HOST = 'host'
DHCP_LEASES_FNAME = 'leases'
DHCP_PID_FNAME = 'pid'
# ovs_lib.py
FAILMODE_SECURE = 'secure'
# linuxbridge.py
BRIDGE_NAME_PREFIX = "qbr-"
# ipset_manager.py
# an ipset prefix chain name
IP_SET_PREFIX_NAME = 'NIPv4'

