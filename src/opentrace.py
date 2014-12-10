#!/usr/bin/env python

import sys
import os

import getopt
import subprocess

# ----------------------------
# opentrace.py - Trace open syscalls via SystemTap or DTrace
# supports filtering per UID or PID

usage = '''opentrace.py [-S|-D] [-p PID | -c "COMMAND" | -u UID]

-S - Call SystemTap
-D - Call DTrace 
-p - Filter by PID
-u - Filter by UID
-c - Run subcommand and filter by it's pid

Environment variables:
    STAP_PATH - path to SystemTap's binary
    DTRACE_PATH - path to DTrace's binary
'''

def error(msg, *args):
    print >> sys.stderr, msg % args
    print >> sys.stderr, usage
    sys.exit(1)

def arg2int(optarg, name):
    try: 
        return int(optarg)
    except TypeError:
        error('Invalid %s - should be integer', name)
    
systemtap   = False
dtrace      = False
filemode    = False

pid         = -1
command     = None
uid         = -1

try:
    options, args = getopt.getopt(sys.argv[1:], 'SDp:c:u:')
except getopt.GetoptError as goe:
    error(str(goe))

# Process command-line options
for opt, optarg in options:
    if opt == '-S':
        systemtap = True
    elif opt == '-D':
        dtrace = True
    elif opt == '-p':
        pid = arg2int(optarg, 'PID')
    elif opt == '-c':
        command = optarg
    elif opt == '-u':
        uid = arg2int(optarg, 'UID')
    
    if pid >= 0 and command is not None:
        error('-p and -c are mutually exclusive')  
    if (pid >= 0 or command is not None) and uid >= 0:
        error('-p or -c are mutually exclusive with -u')    
    if systemtap and dtrace:
        error('-S and -D are mutually exclusive')
            
if not systemtap and not dtrace:
    # Try to guess based on operating system
    systemtap = sys.platform == 'linux2'
    dtrace = sys.platform == 'sunos5'

dtrace_probe = '''
%(name)s 
/%(cond)s/
{
    %(dump)s
}
'''

systemtap_probe = '''
probe %(name)s 
{
    if(%(cond)s) next;
    
    %(dump)s
}
'''

if systemtap:
    if pid >= 0 or command is not None:
        cond = 'pid() != target()'
    elif uid >= 0:
        cond = 'uid() != %d' % uid
    else:
        cond = '0'
    
    entry = {'name': 'syscall.open',
             'cond': cond,
             'dump': '''printf("=> uid: %d pid: %d open: %s %d\\n", 
                        uid(), pid(), filename, gettimeofday_ns());'''}
    ret =   {'name': 'syscall.open.return',
             'cond': cond,
             'dump': '''printf("<= uid: %d pid: %d ret: %d %d\\n", 
                        uid(), pid(), $return, gettimeofday_ns());'''}
    
    # Build command line arguments
    cmdargs = [os.getenv('STAP_PATH', '/usr/bin/stap')]
    if pid >= 0:
        cmdargs.extend(['-x', str(pid)])
    elif command is not None:
        cmdargs.extend(['-c', command])    
    cmdargs.append('-')
    
    stap = subprocess.Popen(cmdargs, stdin=subprocess.PIPE)
    stap.stdin.write(systemtap_probe % entry)
    stap.stdin.write(systemtap_probe % ret)
    
    stap.stdin.close()
    
    stap.wait()
elif dtrace:
    if pid >= 0 or command is not None:
        cond = 'pid == $target'
    elif uid >= 0:
        cond = 'uid == %d' % uid
    else:
        cond = '1'
    
    entry = {'name': 'syscall::open*:entry',
             'cond': cond,
             'dump': '''printf("=> uid: %d pid: %d open: %s %lld\\n", 
                uid, pid, copyinstr(arg1), (long long) timestamp); '''}
    ret =   {'name': 'syscall::open*:return',
             'cond': cond,
             'dump': '''printf("<= uid: %d pid: %d ret: %d %lld\\n", 
                        uid, pid, arg1, (long long) timestamp);'''}

    # Build command line arguments    
    cmdargs = [os.getenv('DTRACE_PATH', '/usr/sbin/dtrace'), '-q']
    if pid >= 0:
        cmdargs.extend(['-p', str(pid)])
    elif command is not None:
        cmdargs.extend(['-c', command])    
    cmdargs.extend(['-s', '/dev/fd/0'])
    
    dtrace = subprocess.Popen(cmdargs, stdin=subprocess.PIPE)
    dtrace.stdin.write(dtrace_probe % entry)
    dtrace.stdin.write(dtrace_probe % ret)
    
    dtrace.stdin.close()
    
    dtrace.wait()
else:
    error('DTrace or SystemTap are non-standard for your platform, please specify -S or -D option')

