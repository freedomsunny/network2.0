# encoding=utf-8

import utils
import shutil
import socket, struct
from IPy import IP
from LogException import *
from config import *

# uid :a port's uid
# net_uid :a network uid
class Dnsmasq_base(object):
    def __init__(self, ip, mask, mac, uid, net_uid, namespace=True):
        self.ip = ip
        self.mac = mac
        self.mask = mask
        self.uid = uid
        self.namespace = namespace
        self.net_uid = net_uid

    def Dnsmsq_cmd(self, args):
        if self.namespace:
            full_args = ["ip", "netns", "exec", NS_DHCP_PREFIX + self._network_uid] + args
            utils.execute(full_args)
        else:
            utils.execute(args)

    def spawn_process(self):
        """Spawns a Dnsmasq process for the network."""
        cmd = [
            'dnsmasq',
            '--no-hosts',
            '--no-resolv',
            '--strict-order',
            '--bind-interfaces',
            '--interface=%s' % self._interface,
            '--dhcp-hostsfile=%s' % self._host,
            '--except-interface=lo',
            '--pid-file=%s' % self._pid_file,
            '--dhcp-range=tag0,%s,static,infinite' % self._network,
            '--dhcp-option=3,%s' % self._gateway,
            '--dhcp-no-override',
            '--dhcp-leasefile=%s' % self._leases_file,
            ]
        self.write_host_info()
        return self.Dnsmsq_cmd(cmd)

    def kill_process(self):
        if self._pid:
            cmd = [
                'kill -9 %d' % self._pid,
            ]
            return utils.execute(cmd)

    def reload_process(self):
        if self._pid:
            cmd = [
                'kill -HUP %d' % self._pid,
            ]
            return utils.execute(cmd)

    def remove_vm_host_info(self):
        Flines = []
        try:
            with open(self._host, 'r+') as f:
                lines = f.readlines()
                for line in lines:
                    if line.find(self.mac) == 0:
                        continue
                    Flines.append(line)
                f.seek(0)
                f.truncate()
                f.writelines(Flines)
        except IOError as e:
            msg = "Error unable open file {}. Msg: {}".format(self._leases_file, e)
            print(msg)
            LogExceptionHelp.logException(msg)
            return False

    def remove_vm_dhcp_file(self):
        try:
            shutil.rmtree(self._vm_dhcp_path)
            return True
        except Exception as e:
            msg = "canot remove vm dhcp file {} msg: {}".format(self._vm_dhcp_path, e)
            print(msg)
            LogExceptionHelp.logException(msg)
            return False

    def write_host_info(self):
        if self.ip and self.mac:
            try:
                with open(self._host, 'a+') as f:
                    f.write("%s,%s\n" % (self.mac, self.ip,))
                # when added a host info to file. you must reload process
                self.reload_process()
            except Exception as e:
                print(e)
                LogExceptionHelp.logException(u"Error unable to open file. Msg: {}".format(e))

    @property
    def _mkdir_full_path(self):
        if not self.uid:
            msg = "_mkdir_full_path,no uid check uid"
            print msg
            LogExceptionHelp.logException(msg)
            return False
        full_file_path = DHCP_CONFIG_FILE_PREFIX + self._uid
        if os.path.isdir(full_file_path):
            return full_file_path + os.sep
        else:
            try:
                os.makedirs(full_file_path)
                return full_file_path + os.sep
            except Exception as e:
                print("Create file {} Error Msg: {}".format(full_file_path, e))
                LogExceptionHelp.logException("Create file {} Error {}".format(full_file_path, e))
                return False

    @property
    def _host(self):
        if not self.uid:
            msg = "_host,dhcp no uid. check uid"
            print msg
            LogExceptionHelp.logException(msg)
        return self._mkdir_full_path + DHCP_HOST

    @property
    def _vm_dhcp_path(self):
        if not self.uid:
            msg = "_vm_dhcp_path, dhcp no uid. check uid"
            print msg
            LogExceptionHelp.logException(msg)
            return False
        return DHCP_CONFIG_FILE_PREFIX + self._uid

    @property
    def _pid(self):
        if os.path.isfile(self._pid_file):
            try:
                with open(self._pid_file, 'r') as f:
                    pid = f.read()
                    return int(pid) if pid  else False
            except IOError:
                msg = 'Error: Unable to access {}'.format(self._pid_file)
                print(msg)
                LogExceptionHelp.logException(msg)
                return False

    @property
    def _network(self):
        if not self.ip:
            msg = "_network,no ip,check ipaddress"
            print msg
            LogExceptionHelp.logException(msg)
        Network = str(IP(self.ip).make_net(self.mask)).split('/')[0]
        return Network

    @property
    def _interface(self):
        return NS_DHCP_INTERFACE_PREFIX + self._uid

    @property
    def _gateway(self):
        if not self._network:
            msg = "_gateway, no network check network"
            print msg
            LogExceptionHelp.logException(msg)
            return False
        Network = str(IP(self._network).make_net(self.mask)).split('/')[0]
        Availed_ip = 2 ** (32 - self.mask) - 2
        dhcp_int = socket.ntohl(struct.unpack("I", socket.inet_aton(Network))[0])
        dhcp_gateway = socket.inet_ntoa(struct.pack('I', socket.htonl(dhcp_int + Availed_ip)))
        return dhcp_gateway

    @property
    def _pid_file(self):
        if not self.uid:
            msg = "_pid_file,dhcp no uid. check uid"
            print msg
            LogExceptionHelp.logException(msg)
        return self._mkdir_full_path + DHCP_PID_FNAME

    @property
    def _leases_file(self):
        return self._mkdir_full_path + DHCP_LEASES_FNAME

    @property
    def _uid(self):
        if not self.uid:
            msg = "_uid,Error: uid is none"
            print msg
            LogExceptionHelp.logException(msg)
            return
        return self.uid[:UID_PREFIX_BIT]

    @property
    def _network_uid(self):
        if not self.net_uid:
            msg = "_network_uid: network uid is none"
            print msg
            LogExceptionHelp.logException(msg)
            return
        return self.net_uid[:UID_PREFIX_BIT]
