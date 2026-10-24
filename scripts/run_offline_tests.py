"""Linux QA launcher: deny outbound networking, including native dependencies.

No test is skipped or modified. The inherited seccomp filter blocks connect
and datagram/message sends before pytest or any optional native AI import.
This runner is a QA boundary, not a Windows product dependency.
"""
import ctypes
import errno
import os
import runpy
import socket
import sys


def main():
    if sys.platform!='linux':raise SystemExit('This network-isolated QA launcher requires Linux')
    os.environ['DOTNET_CLI_TELEMETRY_OPTOUT']='1'
    os.environ['DO_NOT_TRACK']='1'
    os.environ['OTEL_SDK_DISABLED']='true'
    lib=ctypes.CDLL('libseccomp.so.2',use_errno=True)
    lib.seccomp_init.argtypes=[ctypes.c_uint32];lib.seccomp_init.restype=ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];lib.seccomp_syscall_resolve_name.restype=ctypes.c_int
    lib.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    lib.seccomp_load.argtypes=[ctypes.c_void_p];lib.seccomp_release.argtypes=[ctypes.c_void_p]
    context=lib.seccomp_init(0x7fff0000)
    if not context:raise SystemExit('Cannot initialize offline filter')
    for name in [b'connect',b'sendto',b'sendmsg',b'sendmmsg']:
        call=lib.seccomp_syscall_resolve_name(name)
        if call>=0 and lib.seccomp_rule_add(context,0x00050000|errno.EPERM,call,0)!=0:raise SystemExit('Cannot install offline rule')
    if lib.seccomp_load(context)!=0:raise SystemExit('Cannot activate offline filter')
    lib.seccomp_release(context)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as probe:
        for action in [lambda:probe.connect(('127.0.0.1',9)),lambda:probe.sendto(b'offline-test',('127.0.0.1',9))]:
            try:action()
            except PermissionError:pass
            else:raise SystemExit('Offline filter verification failed')
    print('OFFLINE QA: native connect/send syscalls blocked; inherited by child processes.',flush=True)
    sys.path.insert(0,os.getcwd());sys.argv=['pytest',*sys.argv[1:]];runpy.run_module('pytest',run_name='__main__')

if __name__=='__main__':main()
