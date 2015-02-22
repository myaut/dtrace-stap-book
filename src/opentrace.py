#!/usr/bin/env python

import sys, os, subprocess, platform
from optparse import OptionParser

# ----------------------------
# opentrace.py - Trace open syscalls via SystemTap or DTrace
# supports filtering per UID or PID

optparser = OptionParser()

optparser.add_option('-S', '--stap', action='store_true',    
                     dest='systemtap', help='Run SystemTap')
optparser.add_option('-D', '--dtrace', action='store_true',   
                     dest='dtrace', help='Run DTrace')
optparser.add_option('-p', '--pid', action='store', type='int', 
                     dest='pid', default='-1', metavar='PID',
                     help='Trace process with specified PID')
optparser.add_option('-u', '--uid', action='store', type='int', 
                     dest='uid', default='-1', metavar='UID', 
                     help='Filter traced processes by UID')
optparser.add_option('-c', '--command', action='store', type='string', 
                     dest='command', metavar='CMD', 
                     help='Run specified command CMD and trace it')

(opts, args) = optparser.parse_args()

if opts.pid >= 0 and opts.command is not None:
    optparser.error('-p and -c are mutually exclusive')  
if (opts.pid >= 0 or opts.command is not None) and opts.uid >= 0:
    optparser.error('-p or -c are mutually exclusive with -u')    
if opts.systemtap and opts.dtrace:
    optparser.error('-S and -D are mutually exclusive')
            
if not opts.systemtap and not opts.dtrace:
    # Try to guess based on operating system
    opts.systemtap = sys.platform == 'linux2'
    opts.dtrace = sys.platform == 'sunos5'
if not opts.systemtap and not opts.dtrace:
    optparser.error('DTrace or SystemTap are non-standard for your platform, please specify -S or -D option')

def run_tracer(entry, ret, cond_proc, cond_user, cond_default, 
               env_bin_var, env_bin_path, 
               opt_pid, opt_command, args, fmt_probe):    
    cmdargs = [os.getenv(env_bin_var, env_bin_path)]
    if opts.pid >= 0:
        cmdargs.extend([opt_pid, str(opts.pid)])
        entry['cond'] = ret['cond'] = cond_proc
    elif opts.command is not None:
        cmdargs.extend([opt_command, opts.command])    
        entry['cond'] = ret['cond'] = cond_proc
    elif opts.uid >= 0:
        entry['cond'] = ret['cond'] = cond_user % opts.uid
    else:
        entry['cond'] = ret['cond'] = cond_default
    cmdargs.extend(args)
    
    proc = subprocess.Popen(cmdargs, stdin=subprocess.PIPE)
    proc.stdin.write(fmt_probe % entry)
    proc.stdin.write(fmt_probe % ret)
    
    proc.stdin.close()    
    proc.wait()

if opts.systemtap:
    entry = {'name': 'syscall.open',
             'dump': '''printf("=> uid: %d pid: %d open: %s %d\\n", 
                        uid(), pid(), filename, gettimeofday_ns());'''}
    ret =   {'name': 'syscall.open.return',
             'dump': '''printf("<= uid: %d pid: %d ret: %d %d\\n", 
                        uid(), pid(), $return, gettimeofday_ns());'''}
    
    run_tracer(entry, ret, cond_proc = 'pid() != target()', 
               cond_user = 'uid() != %d', cond_default = '0', 
               env_bin_var = 'STAP_PATH',   
               env_bin_path = '/usr/bin/stap', 
               opt_pid = '-x', opt_command = '-c',
               args = ['-'],
               fmt_probe = ''' probe %(name)s {
                    if(%(cond)s) next;
                    
                    %(dump)s
                }
                ''' )
elif opts.dtrace:
    # In Solaris >= 11 open is replaced with openat    
    is_sol11 = int(platform.release().split('.')[-1]) >= 11
    sc_name = 'openat*' if is_sol11 else 'open*'
    fn_arg = 'arg1' if is_sol11 else 'arg0'
    
    entry = {'name': 'syscall::%s:entry' % sc_name, 
        'dump': '''printf("=> uid: %%d pid: %%d open: %%s %%lld\\n", 
        uid, pid, copyinstr(%s), (long long) timestamp); ''' % fn_arg}
    ret =   {'name': 'syscall::%s:return' % sc_name,
        'dump': '''printf("<= uid: %d pid: %d ret: %d %lld\\n", 
                uid, pid, arg1, (long long) timestamp);'''}

    run_tracer(entry, ret, cond_proc = 'pid == $target', 
               cond_user = 'uid == %d', cond_default = '1', 
               env_bin_var = 'DTRACE_PATH', 
               env_bin_path = '/usr/sbin/dtrace', 
               opt_pid = '-p', opt_command = '-c', 
               args = ['-q', '-s', '/dev/fd/0'],
               fmt_probe = ''' %(name)s 
                /%(cond)s/
                {
                    %(dump)s
                }
                ''' )