# encoding=utf-8

from config import *
import utils
from LogException import *

# Default timeout for ovs-vsctl command
DEFAULT_OVS_VSCTL_TIMEOUT = 10

# Special return value for an invalid OVS ofport
INVALID_OFPORT = '-1'


# this class is outside API
# br_name: ovs bridge's name
class BaseOVS(object):
    def __init__(self, br_name=None):
        self.vsctl_timeout = ovs_vsctl_timeout
        self.br_name = br_name

    # 执行ovs-vsctl命令的前缀
    def run_vsctl(self, args):
        full_args = ["ovs-vsctl", "--timeout=%d" % self.vsctl_timeout] + args
        try:
            return utils.execute(full_args)
        except Exception as e:
            print(e)

    # 添加一个OVS桥
    def add_bridge(self, bridge_name, secure_mode=False):
        cmd = ["--", "--may-exist", "add-br", bridge_name]
        if secure_mode:
            cmd += ["--", "set-fail-mode", bridge_name, FAILMODE_SECURE]
        self.run_vsctl(cmd)

    # 删除一个OVS桥
    def delete_bridge(self, bridge_name):
        self.run_vsctl(["--", "--if-exists", "del-br", bridge_name])

    # 检查OVS桥是否存在
    def bridge_exists(self, bridge_name):
        ret = self.run_vsctl(['br-exists', bridge_name])
        if ret[0]:
            print("No search bridge name '{}'".format(bridge_name))
            return False
        return True

    # 查找该接口属于哪个OVS桥
    def get_bridge_name_for_port_name(self, port_name):
        ret = self.run_vsctl(['port-to-br', port_name])
        if ret[0]:
            print("No search port's bridge".format(port_name))
            return False
        return ret[1]

    # 检查OVS桥中是否存在该端口
    def port_exists(self, port_name):
        return bool(self.get_bridge_name_for_port_name(port_name))

    # 添加一个端口
    def add_port(self, port_name):
        self.run_vsctl(["--", "--may-exist", "add-port", self.br_name,
                        port_name])

    # 添加一个内部接口
    def add_port_internal(self, port, vlan=None):
        cmd = [
            'add-port',
            self.br_name,
            port,
            "--",
            "set",
            "interface",
            port,
            "type=internal"
        ]
        if vlan:
            cmd.insert(3, "tag={}".format(vlan))

        self.run_vsctl(cmd)

    # 删除一个端口
    def delete_port(self, port_name):
        self.run_vsctl(["--", "--if-exists", "del-port", self.br_name,
                        port_name])

    # 执行ofctl的前缀命令
    def run_ofctl(self, cmd, args, ):
        full_args = ["ovs-ofctl", cmd, self.br_name] + args
        ret = utils.execute(full_args)
        if ret[0]:
            return False
        return ret

    # 统计有多少条流策略
    def count_flows(self):
        ret = self.run_ofctl("dump-flows", [])
        state_code, result = ret
        if state_code:
            LogExceptionHelp.logException("exec command Error msg: {}".format(result))
            return False
        result = result.split("\n")[1:]
        return len(result) - 1

    # 删除桥上的所有流策略
    def remove_all_flows(self):
        self.run_ofctl("del-flows", [])

    # get port's openflow port id
    def get_port_ofport(self, port_name):
        ofport = self.db_get_val("Interface", port_name, "ofport")
        # This can return a non-integer string, like '[]' so ensure a
        # common failure case
        try:
            int(ofport)
            return ofport
        except (ValueError, TypeError):
            return INVALID_OFPORT

    # get bridge's datapath id  note: datapath id == bridge id
    def get_datapath_id(self):
        return self.db_get_val('Bridge',
                               self.br_name, 'datapath_id').strip('"')

    # 流策略控制
    # action  ：add/mod/del
    # kwargs_list  ： {key:value,key:value.....}
    def do_action_flows(self, action, kwargs_list):
        flow_strs = [_build_flow_expr_str(kw, action) for kw in kwargs_list]

        if action == 'add' or action == 'mod':
            option = '{}-flow'.format(action)

        if action == 'del':
            option = '--strict {}-flows'.format(action)
        self.run_ofctl(option, flow_strs)

    # 添加流策略
    # kwargs  ：{key:value,key:value.....}
    def add_flow(self, **kwargs):
        self.do_action_flows('add', [kwargs])

    # 修改流策略
    # kwargs  ：{key:value,key:value.....}
    def mod_flow(self, **kwargs):
        self.do_action_flows('mod', [kwargs])

    # 删除流策略
    # kwargs  ：{key:value,key:value.....}
    def delete_flows(self, **kwargs):
        self.do_action_flows('del', [kwargs])

    # OVS与OVS之间互连的虚拟线路(需要调用2次)
    def add_patch_port(self, local_name, remote_name):
        self.run_vsctl(["add-port", self.br_name, local_name,
                        "--", "set", "Interface", local_name,
                        "type=patch", "options:peer=%s" % remote_name])
        return self.get_port_ofport(local_name)

    def db_get_map(self, table, record, column):
        state_code, output = self.run_vsctl(["get", table, record, column])
        if state_code:
            return {}
        output_str = output.rstrip("\n\r")
        return self.db_str_to_map(output_str)

    def db_get_val(self, table, record, column):
        sate_code, output = self.run_vsctl(["get", table, record, column])
        if sate_code:
            return
        return output.rstrip("\n\r")

    def db_str_to_map(self, full_str):
        list = full_str.strip("{}").split(", ")
        ret = {}
        for e in list:
            if e.find("=") == -1:
                continue
            arr = e.split("=")
            ret[arr[0]] = arr[1].strip("\"")
        return ret

    # 返回桥上的所有接口
    def get_port_name_list(self):
        state_code, res = self.run_vsctl(["list-ports", self.br_name])
        if state_code:
            return []
        return res.strip().split("\n")

    # 获取接口状态
    def get_port_stats(self, port_name):
        return self.db_get_map("Interface", port_name, "statistics")

    def get_xapi_iface_id(self, xs_vif_uuid):
        args = ["xe", "vif-param-get", "param-name=other-config",
                "param-key=nicira-iface-id", "uuid=%s" % xs_vif_uuid]
        try:
            return utils.execute(args).strip()
        except Exception as e:
            print "Unable to execute %(cmd)s. Exception: %(exception)s" % \
                  ({'cmd': args, 'exception': e})
            return False

    # 设置ovs接口的vlan_tag
    def set_port_tag(self, vlan_tag, port):
        args = ['set', 'port', '%s' % port, 'tag=%d' % vlan_tag]
        self.run_vsctl(args)


    # 添加数据镜像
    def data_mirror(self, vlan=Mirror_vlan):
        args = ['-- add bridge %s mirrors @m -- --id=@m create mirror name=mymirror' % self.br_name,
                'set mirror mymirror select_all=1',
                'set mirror mymirror output_vlan=%d' % vlan
                ]
        for arg in args:
            self.run_vsctl([arg], )

    # 移除数据镜像
    def remove_data_mirror(self):
        args = ['clear Bridge %s mirrors' % self.br_name,
                ]
        self.run_vsctl(args, )

    # 检查是否已经数据镜像
    def is_exsit_mirror(self):
        args = ["list Bridge %s | grep -E '^mirrors'" % self.br_name
                ]
        code, ret = self.run_vsctl(args, )
        ret_len = len(ret.split(':')[1].strip())
        if ret_len <= 2 or code:
            return False
        return True


# 接口属于哪个桥
def get_bridge_for_iface(iface):
    args = ["ovs-vsctl", "--timeout=%d" % ovs_vsctl_timeout,
            "iface-to-br", iface]
    state_code, ret = utils.execute(args, )
    if state_code:
        print "Error at ovs_lib.py line 223. msg: {}".format(ret)
        return
    return ret.strip()


# 获取所有的桥
def get_bridges():
    args = ["ovs-vsctl", "--timeout=%d" % ovs_vsctl_timeout,
            "list-br"]
    state_code, ret = utils.execute(args, )
    if state_code:
        print "Error at ovs_lib.py line 235. msg: {}".format(ret)
        return
    return ret.strip().split("\n")


# 根据key,value生成流表
# flow_dict ：{key:value,key:value}
# cmd       ：'add'/'mod'/'del'
# return [match1=value1,match2=value2,actions=normal]
def _build_flow_expr_str(flow_dict, cmd):
    flow_expr_arr = []
    actions = None

    if cmd == 'add':
        flow_expr_arr.append("hard_timeout=%s" %
                             flow_dict.pop('hard_timeout', '0'))
        flow_expr_arr.append("idle_timeout=%s" %
                             flow_dict.pop('idle_timeout', '0'))
        if 'priority' in flow_dict:
            flow_expr_arr.append("priority=%s" %
                                 flow_dict.pop('priority'))

    if cmd != 'del':
        if "actions" not in flow_dict:
            print ("Must specify one or more actions on flow addition"
                   " or modification")
            return False
        actions = "actions=%s" % flow_dict.pop('actions')

    if cmd == 'del':
        flow_dict.pop('actions', None)
        flow_dict.pop('priority', None)

    for key, value in flow_dict.iteritems():
        if key == 'proto':
            flow_expr_arr.append(value)
        else:
            flow_expr_arr.append("%s=%s" % (key, str(value)))

    if actions:
        flow_expr_arr.append(actions)

    return ','.join(flow_expr_arr)
