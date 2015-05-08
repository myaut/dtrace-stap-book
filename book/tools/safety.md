### Safety and errors

Like we said, dynamic tracing is intended to be safely used in production systems, but since it is intrusive to an OS kernel, there is a room for unsafe actions:
 * Fatal actions inside kernel like reading from invalid pointer (like `NULL`) or division by zero will cause a panic following by a reboot.
 * If probes are executed for too much time (or too often), it will induce performance degradation in a production system, or at least give results that are very different than from a non-traced system (i.e. making racing condition you debug very rare). 
 * Dynamic tracing systems allocate memory for their internal memory which should be limited .
 
That leads to a common principle for all dynamic tracing systems: __add some checks before executing actual tracing__. For example, DTrace has _Deadman Mechanism_ that detects system unresponsiveness induced by DTrace and aborts tracing, while SystemTap monitors time spent in each tracing probe. The common error messages you'll see due to that are `processing aborted: Abort due to systemic unresponsiveness` in DTrace and `SystemTap probe overhead exceeded threshold`. 

Unfortunately, SystemTap is not that affective as DTrace, so probe overhead error message is a common thing. To overcome this error in SystemTap you can recompile your script with `-t` option to see what probes are causing overload and try to optimize them. You may also increase threshold by setting compile macro (with `-D` option) `STP_OVERLOAD_THRESHOLD` in percent of overall CPU time or completely disable it with `STP_NO_OVERLOAD` macro (lastest SystemTap versions support it via `-g --suppress-time-limits`).

Another resource that is limited is memory, which is solved pretty simple: all allocations should be performed when script is launched and with a fixed size. For associative arrays, SystemTap limits number of entries it can hold (changeable by setting macro `MAXMAPENTRIES`), and `ERROR: Array overflow, check MAXMAPENTRIES near identifier 't' at <input>:1:30`, while DTrace limits overall space for them via `dynvarsize` tunable and it will print it as `dynamic variable drops` error. Note that SystemTap still can exhaust memory if you create too many associative arrays, but this will be handled by OOM which will simply kill `stap` tool. Both DTrace and SystemTap limit size of strings used in scripts.

Transport buffer between probes and consumer is also limited, so if you will print in probes faster than consumer can take, you will see `There were NN transport failures` error in SystemTap or `DTrace drops on CPU X` error on DTrace. The answer to that problem is simple: be less verbose, take data from buffer more frequently (regulated by `cleanrate` tunable in DTrace) or increase buffer size (`-b` option and `bufsize` tunable in DTrace and `-s` option in SystemTap).
 
Neither DTrace nor SystemTap are also use special handlers for in-kernel pagefaults, that will disable panic and handle fault if it was caused by tracing. For example DTrace will complain with `error on enabled probe ID 1 (ID 78: syscall::read:entry): invalid alignment (0x197) in action #1 at DIF offset 24` and continue execution, while SystemTap will print `ERROR: read fault [man error::fault] at 0x00000000000024a8 (addr) near operator '@cast' at <input>:1:45` and stop tracing. Note that SystemTap provides more context than DTrace. That is because error-checking is performed in generated C code, not by RISC-VM inside driver.

#### Demonstration scripts

These scripts have errors which cause error messages described above. For associative arrays we will use timestamp to flood array with unrepeated data:
```
# dtrace -n 'int t[int]; 
	tick-1ms { 
		t[timestamp] = timestamp }'
# stap -e 'global t; 
	probe timer.ms(1) {
		t[local_clock_ns()] = local_clock_ns(); }'
```

To demostrate segmentation violation, we will interpret wrong integral argument (fd for Solaris and file position in Linux) as pointer to a thread structure and try to access its field.
```
# dtrace -n 'syscall::read:entry { 
	trace(((kthread_t*) arg0)->t_procp); }' -c 'cat /etc/passwd'
# stap -e 'probe kernel.function("vfs_read") { 
	println(@cast($count, "task_struct")->pid); }' -c "cat /etc/passwd"
```

#### References 

 * ![image:staplang](icons/staplang.png) [Safety and security](https://sourceware.org/systemtap/langref/SystemTap_overview.html#SECTION00026000000000000000)
 * ![image:dtraceicon](icons/dtrace.png) [Performance Considerations](http://docs.oracle.com/cd/E19253-01/817-6223/chp-perf/index.html)
 * SystemTap Wiki: [Exhausted resources](http://sourceware.org/systemtap/wiki/TipExhaustedResourceErrors)