### Tracing

Operating system and application are crucial parts of a computer system, but due to their colossal complexity, there are situations related to software bugs, incorrect system setup that lead to incorrect behavior. To address this issues, system admistrator should perform _instrumentation_ which depends on the issue arisen: it could be performance statistics collection and their analysis, debug or system audit. Two common approaches to _instrumentation_ are _sampling_ when you collect state of the system: values of some variables, stacks of threads, etc. at unspecified moments of time and _tracing_ when you install probes at specified places of software. _Profiling_ is most famous example of _sampling_. 

_Sampling_ is very helpful when you do not know where issue happens, but it hardly help when you try to know why it happened. I.e. profiling revealed that some function, say `foo()` that processes lists of elements, consumes 80% of the time, but doesn't say why: whether some lists are too long, or they should be pre-sorted, or list is inappropriate data structure for `foo()`, or whatever. With _tracing_ we can install a probes to that function, gather information on lists (say their length) and collect cumulative execution of function `foo()`, and then cross-reference them, searching for a pattern in lists which processing cost too much CPU time.

Over time operating system kernels grown different methods of tracing. First one and a simplest one is __counters__ -- each time probe fires (say, major page fault), they increase some counter. Counters may bee than read through kstat interface in Solaris:
```
	# kstat -p |grep maj_fault
	cpu:0:vm:maj_fault      7588
```

Linux usually provides counters through `procfs` or `sysfs`:
```
	# cat /proc/vmstat  | grep pgmajfault
	pgmajfault 489268
```

This approach is limited: you can't add counter for every event without losing performance, and they are usually system-wide (i.e. you can't know what process causing major-faults), or process/thread-wide. 

More complex approach is __debug printing__: add a `printk()` or `cmn_err()` statement as a probe, but this approach is quite limited, because you need recompile kernel each time you need new set of probes (like LTTng does). But if all debug printing will be enabled, you will get excessive system load. By default, most of debug printing in Solaris are disabled unless you compile a DEBUG-build, which is not publicly available. Modern Linux kernels however developed a dynamic debugging facility available via `pr_debug()`. There are several __static probes__ which are deactivated on systems start, but can be activated externally: _ftrace_ and _kprobes_ in Linux and _TNF_ on Solaris, but amount of information provided by them is still limited, and _ftrace_/_kprobes_ are requiring writing kernel modules which is not convenient and dangerous. 

So, generally speaking, that approaches provide very limited set of data at very limited set of tracing points. The only approach that widens that limits is __kernel debugger__, but because each breakpoint halts system, __it cannot be used on production systems__. The answer to them are __dynamic tracing__ which is the topic of this book.