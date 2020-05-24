#! /usr/bin/env python3
"""
This module is a wrapper of 'subprocess' module, which allows you to spawn new bash processes,
and connect to their input/output/error pipes, and obtain their return codes.

Main API
======
run(....):          Run a bash command and wait for completion or timeout,
                    then return a Bash instance
Bash(....):  A class flexibly on executing a bash command in a new process

Constants
------
DEVNULL: Same in 'subproces' module
PIPE:    Same in 'subproces' module
STDOUT:  Same in 'subproces' module

_BASH:         Location of bash program

_S_RUN:        Means that current process is running
_S_COMPLETE:   Means that current process is completed
_S_TIMEOUT:    Means that current process is timeout and killed
_S_KILL:       Means that current process is killed by hand

_D_ARGS:       Default arguments of bash program
_D_MAX_TIME:   Default max time, only used in 'run' method
_D_E_CODES:    Default exepcted returncodes
_D_CWD:        Default executing directory

_L_MAX_TIME:   Maxmium time upper-limitation
"""
import os
import time
import subprocess

_BASH = '/usr/bin/bash'

_S_RUN = 'running'
_S_COMPLETE = 'completed'
_S_TIMEOUT = 'timeout'
_S_KILL = 'killed'

_D_ARGS = []
_D_E_CODES = [0]
_D_MAX_TIME = 60
_D_CWD = os.path.abspath('.')

_L_MAX_TIME = 60 * 60 * 24 * 2

PIPE = subprocess.PIPE
DEVNULL = subprocess.DEVNULL
STDOUT = subprocess.STDOUT

_LOG_FILE_PATH = '/tmp/BASH_LOG_' + str(time.time())

class BashError(Exception):
    """
    Re-raise most errors in 'subprocess' module

    Arguments:
        args:       list[str]       arguments of current bash program
        cmd:        str             command of current bash progrmd
        msg:        str             message comes from error rasied by 'subprocess' module

    Attributes:
        _args, _cmd, _msg
    """
    def __init__(self, args, cmd, msg):
        """ Create a BashError instance """
        super(BashError, self).__init__()
        self._args = args
        self._cmd = cmd
        self._msg = msg

    def __str__(self):
        return 'Error on' + repr(_BASH) + os.linesep \
            + 'Args:' + repr([repr(s) for s in self._args]) + os.linesep \
            + 'Cmd :' + self._cmd + os.linesep \
            + 'Msg :' + self._msg + os.linesep


class Bash(object):
    """
    A class for flexbly executing a bash command in a new process

    Arguments:
        cmd:        str,        command which will be exeucted by bash
        args:       list[str]   bash executing arguments
        stdin:                  same in 'subprocess'
        stdout:                 same in 'subprocess'
        stderr:                 same in 'subprocess'
        cwd:                    same in 'subprocess'
        evn:                    same in 'subprocess'
        e_codes:    list[int],  expected returncodes of current process
        m_time:     int         max time that current process is allowed executing

    Attributes:
        cmd, args, code, stdout, stderr, stdin,
        pid, status, start_time, end_time, m_time, _process

    Methods:
        communicate, check_code, is_complete, is_timeout, kill
    """
    def __init__(self, cmd, args=_D_ARGS,
                 stdin=None, stdout=None, stderr=None,
                 cwd=_D_CWD, env=None, m_time=_D_MAX_TIME, e_codes=_D_E_CODES):
        """
        Create new Bash instance
        Max time is limited in [0 - _L_MAX_TIME]
        """
        def f():
            """Create a group of processes and set id same as current bash process """
            os.setpgrp()

        self.args = [_BASH] + args + ['-c']
        self.cmd = cmd
        try:
            Popen = subprocess.Popen
            i = PIPE if stdin not in [None, PIPE, DEVNULL] else stdin
            process = Popen(args=self.args + [self.cmd],
                            stdin=i, stdout=stdout, stderr=stderr,
                            bufsize=-1, executable=None, preexec_fn=f, close_fds=True,
                            cwd=cwd, env=env, start_new_session=False, universal_newlines=True)
            if stdin not in [None, PIPE, DEVNULL]:
                process.stdin.write(stdin)
                process.stdin.close()
        except Exception as e:
            raise BashError(self.args, self.cmd, str(e))
        self._process = process
        self.stdin = str()
        self.stdout = str()
        self.stderr = str()
        self.code = None
        self.e_codes = e_codes
        self.pid = self._process.pid
        self.s_time = time.time()
        self.e_time = None
        self.m_time = m_time if m_time is not None else _L_MAX_TIME
        self.status = _S_RUN

    def is_complete(self):
        """
        Check if process is completed
        If timeout, kill process and set completed
        Warning: please not check completion by process's status, because of delay of status

        :return: bool
        """
        if self.status != _S_RUN:
            return True
        code = self._process.poll()
        if code is not None:
            self.code = code
            self.status = _S_COMPLETE
            self.e_time = time.time()
            self.stdout, self.stderr = self._process.communicate()
        elif time.time() - self.s_time > self.m_time:
            self._process.kill()
            self._process.wait()
            self.status = _S_TIMEOUT
            self.e_time = time.time()
            self.stdout, self.stderr = self._process.communicate()
        if self.status != _S_RUN:
            self._log()
        return self.status != _S_RUN

    def is_timeout(self):
        """Check if current process is timeout """
        return self.is_complete() and self.status == _S_TIMEOUT

    def check_code(self):
        """Check if returncode of current process is in expect """
        return None if not self.is_complete() else self.code in self.e_codes

    def kill(self):
        """Try to kill current process even though it is completed actually, but status not """
        if not self.is_complete():
            self._process.kill()
            self._process.wait()
            self.e_time = time.time()
            self.stdout, self.stderr = self._process.communicate()
            self.status = _S_KILL

    def _log(self):
        f_time = lambda t : time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))
        if not os.path.exists(os.path.dirname(_LOG_FILE_PATH)):
            os.makedirs(os.path.dirname(_LOG_FILE_PATH))
        with open(file=_LOG_FILE_PATH, mode='a') as f:
            f.write(os.linesep)
            f.write('Cmd    :' + self.cmd + os.linesep)
            f.write('Args   :' + repr(self.args) + os.linesep)
            f.write('Code   :' + str(self.code) + os.linesep)
            f.write('Stdout :' + str(self.stdout) + os.linesep)
            f.write('Stderr :' + str(self.stderr) + os.linesep)
            f.write('S_time :' + f_time(self.s_time) + os.linesep)
            f.write('E_time :' + f_time(self.e_time) + os.linesep)

    def __str__(self):
        return self.__class__.__name__ + '(status=' + repr(self.status) + ', code=' \
            + repr(self.code) + ', args=' + repr(self.args) + ', cmd=' + repr(self.cmd) + ')'


def run(cmd, args=_D_ARGS,
        stdin=None, stdout=None, stderr=None,
        cwd=_D_CWD, env=None, e_codes=_D_E_CODES, m_time=_D_MAX_TIME):
    """Run command and wait complete or timeout, then return a Bash instance """
    process = Bash(cmd=cmd, args=args,
                   stdin=stdin, stdout=stdout, stderr=stderr,
                   cwd=cwd, env=env, e_codes=e_codes, m_time=m_time)
    while process.is_complete() is False:
        pass
    return process

