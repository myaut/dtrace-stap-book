#!/usr/bin/env python

import re
import sys

# ----------------------------
# openproc.py - Collect data from opentrace.py and merge :entry and :return probes 

# Open trace file or use stdin 
try:
    inf = file(sys.argv[1], 'r')
except OSError as ose:
    print ose
    print '''openproc.py [filename]'''
    sys.exit(1)
except IndexError:
    inf = sys.stdin

# Convert time to human time
def human_time(ns):
    ns = float(ns)
    for unit in ['ns', 'us', 'ms']:
        if abs(ns) < 1000.0:
            break
        ns /= 1000.0
    else:
        unit = 's'
    return "%.2f %s" % (ns, unit)

# Parse /etc/passwd and create UID-to-USERNAME map
uid_name = lambda user: (int(user[2]), user[0])    
users = dict([uid_name(user.split(':'))
              for user in file('/etc/passwd')])

# Per-PID state - tuples (start time, file name)
state = {}

# Regular expressions for parsing tracer output
re_entry = re.compile("=> uid: (\d+) pid: (\d+) open: (.*?) (\d+)")
re_return = re.compile("<= uid: (\d+) pid: (\d+) ret: (-?\d+) (\d+)")
    
for line in inf:
    if line.startswith('=>'):
        # :entry probe, extract start time and filename
        m = re_entry.match(line)
        _, pid, fname, tm = m.groups()
        
        state[int(pid)] = (int(tm), fname)
    elif line.startswith('<='):
        # :return probe, get return value, timestamp and print information
        m = re_return.match(line)
        uid, pid, ret, tm = map(int, m.groups())
        
        if pid not in state:
            continue
        
        status = 'FD %d' % ret if ret >= 0 else 'ERROR %d' % ret
        
        print 'OPEN %s %d %s => %s [%s]' % (users.get(uid, str(uid)), 
                                            pid, state[pid][1], status,
                                            human_time(tm - state[pid][0]))
        del state[pid]
