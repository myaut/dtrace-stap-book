### Pre- and post-processing

Despite the flexibility of the dynamic tracing languages, it lacks of common tools to create user-friendly interfaces like command line options to generate different filtering with predicates, sorting and omitting columns, making scripts are hard to reuse. For example, `iosnoop` from DTraceToolkit allows to generate user-printable timestamps or not with `-v` option, filter device or PID with `-d` and `-p` options, and a series of options that enable or disable showing various columns. 

In such cases we can use general purpose scripting language such as Python, Perl or even shell-script to generate dynamic tracing on-the fly, run it, read its output in some form and than print it in human-readable form:

![image:prepost](prepost.png)

For example, let's add the following capabilities to our `open()` system call tracer: customizable per-pid and per-user filters, and also make it universal -- capable running in DTrace and SystemTap.

````` scripts/src/opentrace.py 

First half of this script is an option parser implemented with `OptionParser` Python class and intended to parse command-line arguments, provide help for them and check their correctness -- i.e. mutually-exclusive options, etc. Second half of the script is a `run_tracer()` function that accepts multiple arguments and `if-else` statement that depending on chosen dynamic tracing system, generates parameters for `run_tracer()` as follows:

---
__Parameter__ | __Description__ | __SystemTap__ | __DTrace__
`entry` | entry probe name and body | `syscall.open` | `syscall::open*:entry` or \
                                                       `syscall::openat*:entry` depending on Solaris version
`ret` | return probe name and body | `syscall.open.return` | Similiar to entry probe, but with name `return`
`cond_proc` | predicate for picking a process | `pid() != target()` | `pid == $target`
`cond_user` | predicate template for per-user tracing | `uid() != %d` | `uid == %d`
`cond_default` | always-true predicate | `0` | `1`
`env_bin_var` | environment option used to override path to DTrace/SystemTap binary | `STAP_PATH` | `DTRACE_PATH`
`env_bin_path` | default path to  DTrace/SystemTap binary | `/usr/bin/stap` | `/usr/sbin/dtrace`
`opt_pid` | option for tracing tool accepting PID | `-x` | `-p`
`opt_pid` | option for tracing tool accepting new command | `-c` | `-c`
`args` | arguments to read script from stdin | `-` | `-q -s /dev/fd/0`
`fmt_probe` |3,1 format string for constructing probes
---

So this script generate predicate condition `uid == 100` for the following command-line:
```
# python opentrace.py -D -u 100
```

Post-processing is intended to analyse already collected trace file, but it might be run in parallel with tracing process. However, it allows to defer trace analysis -- i.e. collect maximum data as we can, and then cut out irrelevant data, showing only useful. This can be performed using either Python, Perl, or other scripting languages or even use statical analysis languages like R. Moreover, post-processing allows to reorder or sort tracing output which can also help to avoid data mixing caused by per-process buffers. 

The next script will read `opentrace.py` output, merge information from entry and return probes, and convert user-ids and time intervals to a convenient form. Like in dynamic tracing languages we will use an associative array `states` which is implemented as `dict` type in Python to save data from entry probes and use process ID as a key.

````` scripts/src/openproc.py 

If we pipe `opentrace.py` output to this script, we can get similar data:
```
# python opentrace.py -c 'cat /tmp/not_exists' |
			python openproc.py 
	cat: cannot open /tmp/not_exists: No such file or directory
	[...]
	OPEN root 3584 /tmp/not_exists => ERROR -1 [10.17 us]
	[...]
```

!!! WARN
This is only a demonstration script, and many of their features may be implemented using SystemTap or DTrace. Moreover, they allow to use `system()` calls an external program, for example to parse `/etc/passwd` and get user name. However, it will cost much more, and if this call will introduce more `open()` calls (which it will obviously do), we will get more traced calls and a eternal loop. 
!!!

