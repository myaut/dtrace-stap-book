>>>>> STYLE CheatSheet
>>>>> 0.8 END COND

### Tools

--- %20,40,40
 | _DTrace_ | _SystemTap_
Tool | `dtrace(1M)` | `stap(1)`
List probes | \
   ```
# dtrace <b>-l</b>
# dtrace <b>-l -P io</b>
   ``` | \
   ```
# stap <b>-l 'ioblock.*'</b>
# stap <b>-L 'ioblock.*'</b>
   ```
One-liner | \
   ```
# dtrace <b>-n</b> '
    syscall::read:entry { 
        trace(arg1); } '
   ``` | \
   ```
# stap <b>-e</b> '
    probe syscall.read { 
        println(fd); } '
   ```
Script | \
   ```
# dtrace <b>-s script.d</b>
   ``` \
(optionally add `-C` for preprocessor, `-q` for quiet mode) | \
   ```
# stap <b>script.stp</b>
   ```
Custom probe | \
   ```
# dtrace <b>-P io -n start</b>
   ``` | -
Integer arguments | \
   ```
# dtrace -n '
    syscall::read:entry 
       / cpu == <b>$1</b> / ' <b>0</b>
   ``` | \
   ```
# stap -e '
    probe syscall.read { 
     if(cpu() != <b>$1</b>) next;
       println(fd); } ' <b>0</b>
   ```
String arguments | \
   ```
# dtrace -n '
    syscall::read:entry 
       / execname == <b>$1</b> / ' <b>'"cat"'</b>
   ``` | \
   ```
# stap -e '
    probe syscall.read { 
     if(execname() == <b>@1</b>) 
        println(fd); } ' <b>cat</b>
   ```
Guru/destructive mode (___#red !___) | \
   ```
# dtrace <b>-w</b> ...
   ``` | \
   ```
# stap <b>-g</b> ...
   ```
Redirect to file | \
   ```
# dtrace <b>-o FILE</b> ...
   ``` (appends) | \
   ```
# stap <b>-o FILE</b> ...
   ``` (rewrites) 
Tracing process  | \
   ```
# dtrace -n '
    syscall::read:entry 
       / pid == <b>$target</b> / { ...
         }' <b>-c 'cat /etc/motd'</b>
   ``` (or `-p PID`) | \
   ```
# stap -e '
    probe syscall.read { 
     if(pid() == <b>target()</b>) ...
         } ' <b>-c 'cat /etc/motd'</b>
   ``` (or `-x PID`)
---

### Probe names

--- %18,38,44
            | _DTrace_ | _SystemTap_
Begin/end   | `dtrace:::BEGIN`, `dtrace:::END` | `begin`, `end`
`foo()` entry | `fbt::foo:entry` | `kernel.function("foo")` >>> \
                                   `module("mod").function("foo")`
`foo()` return | `fbt::foo:return` | `kernel.function("foo").return`
Wildcards | `fbt::foo*:entry` | `kernel.function("foo*")`
Static probe `mark` | `sdt:::mark` | `kernel.trace("mark")`
System call | `syscall::read:entry` | `syscall.read`
Timer once per second | `tick-1s` | `timer.s(1)`
Profiling | `profile-997hz` | `timer.profile()`, `perf.*`
`read()` from libc | `pid$target:libc:read:entry` >>> \
                     Traces process with `pid == $target` | \
                     `process("/lib64/libc.so.6").function("read")` >>> \
                     Traces any process that loads libc
---

In DTrace parts of probe name may be omitted: `fbt::foo:entry` -> `foo:entry` >>>
Units for timer probes: `ns`, `us`, `ms`, `s`, `hz`, `jiffies` (SystemTap), `m`, `h`, `d` (all three - DTrace)

>>>>> 0.02 END


!!! F w:0.48

### Printing

--- %22,33,43
 | _DTrace_ | _SystemTap_
Value | `trace(v)` | `print(v)`
Value + newline | - | `println(v)`
Delimited values | - | `printd(",",v1,v2)` >>> \
                       `printdln(",",v1,v2)`
Memory dump | \
    ```
tracemem(
    ptr, 16)
    ``` | `printf("%16M", ptr)`
Formatted |2,1 `printf("%s", str)` 
Backtrace  | \
    ```
<i>u</i>stack(n) 
<i>u</i>stack()
    ``` | \
    ```
print_<i>u</i>backtrace()
print_<i>u</i>stack(
    <i>u</i>backtrace())
    ```
Symbol | \
    ```
<i>u</i>sym(addr) 
<i>u</i>func(addr)
<i>u</i>addr(addr)
    ``` | \
    ```
print(<i>u</i>symname(addr))
print(<i>u</i>symdata(addr))
    ```
---

If _u_ prefix is specified, userspace symbols and backtraces are printed, if not -- kernel symbols are used

### String operations

--- %25,35,40
_Operation_ | _DTrace_ | __SystemTap_
Get from kernel |1,2 `stringof(expr)` >>> \
                       `(string) expr` | `kernel_string*()`
Convert scalar | `sprint()` and `sprintf()`
Copy from user | `copyinstr()` | `user_string*()`
Compare |2,1 `==`, `!=`, `>`, `>=`, `<`, `<=`
Concat | `strjoin(str1, str2)` | `str1 . str2`
Get length |2,1 `strlen(str)`
Check for substring | \
  ```
strstr(
    haystack, 
    needle)
  ``` | \
  ```
  isinstr(
     haystack, 
     needle)
  ```
---

!!!

!!! F x:0.52 w:0.48


### Context variables

---
_Description_ | _DTrace_ | _SystemTap_
Thread | `curthread` | `task_current()`
Thread ID | `tid` | `tid()`
PID | `pid` | `pid()`
Parent PID | `ppid` | `ppid()`
User/group ID | `uid`/`gid` | `uid()`/`gid()` >>> \
                              `euid()`/`egid()`
Executable >>> name | `execname` >>> \
                      `curpsinfo-> ps_fname` | `execname()`
Command line | `curpsinfo-> ps_psargs` | `cmdline_*()`
CPU number | `cpu` | `cpu()`
Probe names | `probeprov` >>> `probemod` >>> \
              `probefunc` >>> `probename` | `pp()` >>> `pn()` >>> `ppfunc()` >>> \
                                         `probefunc()` >>> `probemod()`
---

### Time

--- %24,33,43
_Time source_ | _DTrace_ | _SystemTap_
System timer | `\`lbolt` >>> `\`lbolt64` | `jiffies()`
CPU cycles | - | `get_cycles()`
Monotonic time | `timestamp` | \
  ```
  local_clock_<i>unit</i>()
  ``` >>> \
  ```
  cpu_clock_<i>unit</i>(<i>cpu</i>)
  ```
CPU time of thread | `vtimestamp` | -
Real time | `walltimestamp` | \
  ```
  gettimeofday_<i>unit</i>()
  ```
---

Where _unit_ is one of `s`, `ms`, `us`, `ns`

!!!

>>>>> 0.58

### Aggregations

--- %25,37.5,37.5
_Time source_ | _DTrace_ | _SystemTap_
Add value | \
    ```
@aggr[keys] = <i>func</i>(value);
    ``` | \
    ```
aggr[keys] <<< value;
    ```
Printing | \
    ```
printa(@aggr);
printa("format string", @aggr);
    ``` | \
    ```
foreach([keys] in aggr) {
    print(keys, @<i>func</i>(aggr[keys]));
}
    ```
Clear | \
    `clear(@aggr);` or `trunc(@aggr);` | \
    ```
delete aggr;
    ```
Normalization by 1000 | \
    ```
normalize(@aggr, 1000);
denormalize(@aggr);
    ``` | \
`@func(aggr) / 1000` in printing
Select 20 values | \
    ```
trunc(@aggr, 20);
    ```| \
    ```
foreach([keys] in aggr limit 20) {
    print(keys, @<i>func</i>(aggr[keys]));
}
    ```
Histograms (linear in \[10;100\] with step 5 and logarithmical) | \
    ```
@lin = lquantize(value, 10, 100, 5);
@log = quantize(value);
...
printa(@lin);   printa(@log);
    ``` | \
    ```
aggr <<< value;
...
print(@hist_linear(aggr, 10, 100, 5));
print(@hist_log(aggr));
    ```
---

Where _func_ is one of `count`, `sum`, `min`, `max`, `avg`, `stddev`

>>>>> 0.0 END

### Process management

!!! F 

__SystemTap__

Getting task_struct pointers: 
  * `task_current()` – current task_struct 
  * `task_parent(t)` – parent of task `t` 
  * `pid2task(pid)` – task_struct by pid
  

Working with task_struct pointers: 
  * `task_pid(t)` & `task_tid(t)` 
  * `task_state(t)` – 0 (running), 1-2 (blocked) 
  * `task_execname(t)`

__DTrace__

`kthread_t* curthread` fields: 
  * t_tid, t_pri, t_start, t_pctcpu

`psinfo_t* curpsinfo` fields: 
  * `pr_pid`, `pr_uid`, pr_gid, pr_fname, pr_psargs, pr_start

`lwpsinfo_t* curlwpsinfo` fields: 
  * `pr_lwpid`, `pr_state`/`pr_sname`

`psinfo_t*` and `lwpsinfo_t*` are passed to some `proc:::` probes

!!!

!!! F x:0.54 s:0.6
![image:forkproc](forkproc.png)
!!!

>>>>> 0.27

### Scheduler

!!! F s:0.5
![image:sched](sched.png)
!!!

!!! F x:0.4 w:0.6
---
      | _DTrace_ | _SystemTap_
__1__ | `sched:::dequeue` | `kernel.function("dequeue_task")`
__2__ | `sched:::on-cpu` | `scheduler.cpu_on`
__3__ | `sched:::off-cpu` | `scheduler.cpu_off`
__4__ | `sched:::enqueue` | `kernel.function("enqueue_task")`
__5__ | - | `scheduler.migrate`
__6__ | `sched:::sleep` | -
__7__ | `sched:::wakeup` | `scheduler.wakeup`
---
!!!

>>>>> 0.18

### Virtual memory

!!! F 

##### Probes

__SystemTap__

  * `vm.brk` – allocating heap
  * `vm.mmap` – allocating anon memory
  * `vm.munmap` – freeing anon memory
  
__DTrace__

  * `as_map:entry` – allocating proc mem
  * `as_unmap:entry` – freeing proc mem

!!!

!!! F x:0.4 w:0.6

###### Page faults
---
_Type_ | _DTrace_ | _SystemTap_
_Any_ | `vminfo::as_fault` | `vm.pagefault` >>> \
                             `vm.pagefault.return` >>> \
                             `perf.sw.page_faults`
_Minor_ |  | `perf.sw.page_faults_min`
_Major_ | `vminfo:::maj_fault` | `perf.sw.page_faults_maj`
_CoW_ | `vminfo:::cow_fault` |
_Protection_ | `vminfo:::prot_fault` |
---
!!!

>>>>> 0.18 END

### Block Input-Output

!!! F w:0.4

Block request structure fields:

---
_Field_ | `bufinfo_t` >>> `struct buf` | `struct bio`
Flags | `b_flags` | `bi_flags`
R/W | `b_flags`* | `bi_rw`
Size | `b_bcount` | `bi_size`
Block | `b_blkno` >>> `b_lblkno` | `bi_sector`
Callback | `b_iodone` | `bi_end_io`
Device | `b_edev` >>> `b_dip` | `bi_bdev`
---

\* flags `B_WRITE`, `B_READ` 

!!!

!!! F s:0.6 x:0.44
![image:bio](bio.png)
!!!

>>>>> 0.22

### Network stack

![image:netprobes](netprobes2.png)

### Non-native languages

--- %16,40,44
__Function call__  | _DTrace_ | _SystemTap_
Java* | \
`method-entry`                                  \
  * arg0 — internal JVM thread's identifier     \
  * arg1:arg2 — class name                      \
  * arg3:arg4 — method name                     \
  * arg5:arg6 — method signature              | \
`hotspot.method_entry`                          \
  * thread_id — internal JVM thread's identifier\
  * class — class name                          \
  * method — method name                        \
  * sig — method signature
Perl | \
`perl$target:::sub-entry`                       \
  * `arg0` -- subroutine name                   \
  * `arg1` -- source file name                  \
  * `arg2` -- line number                     | \
`process("...").mark("sub__entry")`             \
  * `$arg1` -- subroutine name                  \
  * `$arg2` -- source file name                 \
  * `$arg3` -- line number
Python | \
`python$target:::function-entry`                \
  * `arg0` -- source file name                  \
  * `arg1` -- function name                   | \
`python.function.entry`                         \
  * `$arg1` -- source file name                 \
  * `$arg2` -- function name
PHP | \
`function-entry`                                \
  * `arg0` — function name                      \
  * `arg1` — file name                          \
  * `arg2` — line number                        \
  * `arg3` — class name                         \
  * `arg4` — scope operator `::`            |   \
`process("...").mark("function__entry")`        \
  * `$arg1` — function name                     \
  * `$arg2` — file name                         \
  * `$arg3` — line number                       \
  * `$arg4` — class name                        \
  * `$arg5` — scope operator `::`
---


___small \*requires `-XX:+DTraceMethodProbes` ___

