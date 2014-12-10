#!/usr/bin/env python

import re
import sys

# ----------------------------
# openproc.py — Collect data from opentrace.py and 
# join :entry and :return probes 

usage = '''openproc.py [filename]'''

def error(msg, *args):
    print >> sys.stderr, msg % args
    print >> sys.stderr, usage
    sys.exit(1)

# Open trace file
try:
    inf = file(sys.argv[1], 'r')
except OSError as ose:
    error(str(ose))
except IndexError:
    inf = sys.stdin

# Parse /etc/passwd and create UID-to-USERNAME map
uid_name = lambda user: (int(user[2]), user[0])
    
users = [uid_name(user.split(':'))
         for user in
         file('/etc/passwd')]
users = dict(users)

# Per-PID state
start = {}
fnames = {}

# Regular expressions for parsing tracer output
re_entry = re.compile("=> uid: (\d+) pid: (\d+) open: (.*?) (\d+)")
re_return = re.compile("<= uid: (\d+) pid: (\d+) ret: (-?\d+) (\d+)")
    
for line in inf:
    if line.startswith('=>'):
        # :entry probe, extract start time and filename
        m = re_entry.match(line)
        _, pid, fname, tm = m.groups()
        
        pid = int(pid)
        tm = int(tm)
        
        start[pid] = tm
        fnames[pid] = fname
    elif line.startswith('<='):
        # :return probe, get return value, timestamp and print information
        m = re_return.match(line)
        uid, pid, ret, tm = map(int, m.groups())
        
        if pid not in start or pid not in fnames:
            continue
        
        if ret < 0:
            status = 'ERROR %d' % ret
        else:
            status = 'FD %d' % ret
        
        print 'OPEN %s %d %s => %s [%d]' % (users.get(uid, str(uid)), 
                                            pid, fnames[pid], status,
                                            tm - start[pid])
        
        del start[pid]
        del fnames[pid]
