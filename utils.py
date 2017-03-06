# encoding=utf-8

import commands
from LogException import *
import subprocess
import signal
import shlex
from eventlet import greenthread


def execute(cmd, return_stdout=True):
    if cmd:
        print "Runing command: {}".format(cmd)
        exec_cmd = '  '.join(cmd)
        ret = commands.getstatusoutput(exec_cmd)
        if ret[0]:
            msg = "Runing command [{}] error. msg: [{}]".format(exec_cmd, ret[1])
            LogExceptionHelp.logException(msg)
            print(msg)
        else:
            print "Commands completed with success"
            return ret


def subprocess_popen(args, stdin=None, stdout=None, stderr=None, shell=False,
                     env=None):
    return subprocess.Popen(args, shell=shell, stdin=stdin, stdout=stdout,
                            stderr=stderr, preexec_fn=_subprocess_setup,
                            close_fds=True, env=env)


def _subprocess_setup():
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def create_process(cmd, root_helper=None, addl_env=None):
    """Create a process object for the given command.

    The return value will be a tuple of the process object and the
    list of command arguments used to create it.
    """
    if root_helper:
        cmd = shlex.split(root_helper) + cmd
    cmd = map(str, cmd)

    print("Running command: {}".format(cmd))
    env = os.environ.copy()
    if addl_env:
        env.update(addl_env)

    obj = subprocess_popen(cmd, shell=False,
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           env=env)

    return obj, cmd


def exec_cmd(cmd, root_helper=None, process_input=None, addl_env=None,
             check_exit_code=True, return_stderr=False, log_fail_as_error=True,
             extra_ok_codes=None):
    try:
        obj, cmd = create_process(cmd, root_helper=root_helper,
                                  addl_env=addl_env)
        _stdout, _stderr = (process_input and
                            obj.communicate(process_input) or
                            obj.communicate())
        obj.stdin.close()
        msg = ("\nCommand: %(cmd)s\nExit code: %(code)s\nStdout: %(stdout)r\n"
               "Stderr: %(stderr)r") % {'cmd': cmd, 'code': obj.returncode,
                                        'stdout': _stdout, 'stderr': _stderr}

        extra_ok_codes = extra_ok_codes or []
        if obj.returncode and obj.returncode in extra_ok_codes:
            obj.returncode = None

        if obj.returncode and log_fail_as_error:
            LogExceptionHelp.logException(msg)
        else:
            LogExceptionHelp.logException(msg)

        if obj.returncode and check_exit_code:
            raise RuntimeError(msg)
    finally:
        # NOTE(termie): this appears to be necessary to let the subprocess
        #               call clean something up in between calls, without
        #               it two execute calls in a row hangs the second one
        greenthread.sleep(0)

    return return_stderr and (_stdout, _stderr) or _stdout
