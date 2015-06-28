### Profiling

Consider the following task: you need to know which functions are called more often than others or spend most time when executing because it makes them perfect targets for code optimization. You may do it by attaching to every function entry and exit point the following script:

```
fbt:::entry { 
	self->start = timestamp; 
} 

fbt:::return 
/self->start/ 
{ 
	@fc[probefunc] = count();
	@ft[probefunc] = avg(timestamp - self->start); 
} 
tick-1s { 
	printa("%s %@d %@d", @fc, @ft); 
	trunc(@fc); trunc(@ft) }
```

!!! DANGER
This script is conceptual! Do not run it on real system. 
!!!

If you were able to collect data with this script, you'll got _population_, but you couldn't do that. Usually function call takes several processor cycles and a single instruction, but when you run it, you'll need hundreds of instructions (for getting timestamp and writing to a aggregation), which causes colossal _overhead_. Statistics theory, however, provides a solution to that: instead of gathering entire population, you may reduce it to a _sample_, which is representative (reproduces significant properties of a population). Collecting a sample is called _sampling_, while sampling function calls is usually referred as _profiling_.

!!! DEF
In software engineering, _profiling_ is a form of dynamic program analysis that measures, for example, the space (memory) or time complexity of a program, the usage of particular instructions, or the frequency and duration of function calls. Most commonly, profiling information serves to aid program optimization.
!!!

Modern operating systems provide builtin profilers, such as __OProfile__ and __SysProf__ in Linux which were replaced with __perf__ subsystem since 2.6.31 kernel or **er\_kernel** from Solaris Studio. However, Dynamic tracing languages allow to build custom profilers. 

A simplest profiler records process ID to see which processes or threads consume CPU resources more than others, as we discussed about [timer probes][lang/probes#timers]. They may be implemented with following DTrace script:
```
# dtrace -qn ' 
	profile-997hz {
		@load[pid, execname] = count(); 
	}
	tick-20s { exit(0); }'
```

Or in SystemTap:
```
# stap -e 'global load; 
	probe timer.profile {
		load[pid(), execname()] <<< 1; }
	probe timer.s(20) {
		exit();
	}'
```

If we want to go down to a function level, we need to access _program counter_ register (or _instruction pointer_ in x86 terminology) each time profiling probe fires. We will refer to program counter as PC later in this book. In DTrace these values are explicitly provided in `arg0` -- PC in kernel mode and `arg1` -- PC in userspace mode in `profiling` probes. Depending on if process was in kernel mode when profiling probe fired or not, `arg0` or `arg1` will be set to 0. Moreover, you may always get current userspace program counter using uregs array: `uregs[REG_PC]`. There is also `caller` and `ucaller` builtin variables. 

You can use `addr()` tapset function in SystemTap which returns userspace PC or kernel PC depending on where probe were fired (some probes do not allow that, so `0` will be returned). To get userspace address explicitly, use `uaddr()` function.

!!! WARN
Note that we were used `profile-997hz` probe to avoid "phasing": if we'd used `profile-1000hz` probe, there were a chance, that all probes were fired while system timer handler is working, thus making profiling useless (we will see that 100% of time kernel spends in system timer). In SystemTap `timer.profile` uses system timer for profiling, but `addr()` and `uaddr()` return correct values. 
!!!

#### CPU performance measurement

Even if you collect PC, you will get what functions use CPU the most, but that doesn't mean that utilize processor resources effictively. For example, it can spend most of the time waiting for memory or cache or reset pipeline due to branch misprediction instead of utilizing ALU for actual computations. Such wasted cycles are referred as _stalled_ in Intel processor documentation. 

Modern processors allow to measure influence of such performance penalties through CPU performance counters. Each time such event happens, CPU increments value of the counter. When counter exceeds threshold, exception is arisen which may be handled by dynamic tracing system. Or, counter may be read from userspace application, for example with `rdpmc` assembly instruction on Intel CPUs. 

You may use `cpustat` tool to get list of available CPU events in Solaris:
```
# cpustat -h
[...]
event0:  cpu_clk_unhalted.thread_p inst_retired.any_p 
```
Description of such events may be found in CPU's documentation. SPARC counters are described in the book "Solaris Application Programming", but it lacks description of newer CPUs (SPARC T3 and later). However, documentation on SPARC T4 and T5 may be found here: [Systems Documentation](http://www.oracle.com/technetwork/server-storage/sun-sparc-enterprise/documentation/sparc-servers-documentation-163529.html). Solaris also provides CPU-independent generic counters which names start with `PAPI` prefix. 

Linux have separate subsystem that is responsible for providing access to CPU performance counters: `perf`. It has userspace utility `perf`, which can show you list of supported events:
```
# perf list
List of pre-defined events (to be used in -e):
	cpu-cycles OR cycles                     [Hardware event]
	instructions                             [Hardware event]
```

You can use userspace tools `perf` in Linux or `cpustat`/`cputrack` in Solaris to gather CPU counters. 

DTrace provides CPU counters through `cpc` provider (which is implemented through separate kernel module). It probe names consists from multiple parameters:
```
<i>EventName</i>-{kernel|user|all}[-<i>Mask</i>]-<i>Number</i>
```
_EventName_ is a name of event taken from `cpustat` output (and matches documentation name in case of Intel CPUs). Following parameter defines a mode: _kernel_ probes only account kernel instructions, _user_ only work for userspace, and _all_ will profile both. _Number_ is a threshold for a counter after which probe will fire. Do not set _Number_ to a small values to avoid overheads and system lockup, 10000 provides is relatively accurate readings. _Mask_ is an optional parameter which allows to filter devices which accounted in performance counters (such as memory controllers or cores) and should be a hexademical number. 

For example, you may use probe `PAPI_l3_tcm-user-10000` to measure number of userspace misses to last-level cache which is L3 cache in our case:
```
# dtrace -n '
	cpc:::PAPI_l3_tcm-user-10000 
	/arg1 != 0/ { 
		@[usym(arg1)] = count(); } 
	END { 
		trunc(@, 20); 
		printa(@); 
	}'
```

SystemTap provides access to CPU counter using `perf` tapset:
```
# stap -l 'perf.*.*'
perf.hw.branch_instructions
[...]
# stap -l 'perf.*.*.*.*'
perf.hw_cache.bpu.read.access
```

[perf]
These probes are actually aliases for the following probes:
```
perf.type(<i>type</i>).config(<i>config</i>)[.sample(<i>sample</i>)][.process("<i>process-name</i>")][.counter("<i>counter-name</i>")]
```
_type_ and _config_ are numbers used in `perf_event_attr` -- their values may be found in header `linux/perf_event.h`. _sample_ is a number of events after which probe firing. _process-name_ allows to monitor only certain processes instead of system-wide sampling and contains name of the process (path to executable). _counter-name_ allows to set an alias for performance counter which will be later used for `@perf` expression (see below). 

To measure last userspace level cache misses in SystemTap, you may use following script:
```
# stap -v -e '
	global misses; 
	probe perf.hw_cache.ll.read.miss { 
		if(!user_mode()) next; 
		misses[probefunc()] <<< 1; 
	} ' -d <path-to-lib>
```

!!! WARN
These examples were tested on Intel Xeon E5-2400 processor. Like we mentioned before, performance counters are CPU-specific.
!!!

SystemTap allows to create per-processor counter which can be read later:
```
# stap -v -t -e '
    probe perf.hw.instructions
        .process("/bin/bash").counter("insns") { } 

    probe process("/bin/bash").function("cd_builtin")  { 
        printf(" insns = %d\n", @perf("insns"));
    }'
```

!!! WARN
There is a bug [PR-17660](https://sourceware.org/bugzilla/show_bug.cgi?id=17660) which can cause `BUG()` in kernel when you use `@perf` in userspace. It seem to be resolved in current SystemTap/Kernel.
!!!