### [__index__:context of probe] [__index__:context function] Context

!!! DEF
_Probe context_ contains system state related to a fired probe, including:
 * Register values
 * Thread and process, which caused probe firing, including CPU where thread is running
 * Currently executing probe
!!!
 
Context is provided as built-in variables in DTrace and BPFTrace such as `execname` or as tapset functions in SystemTap such as `execname()`. 

Userspace register values are available in DTrace through built-in variable `uregs`. In SystemTap, they available through Embedded C and kernel function `task_pt_regs`, or a special Embedded C variable `CONTEXT`, see for example implementation of `uaddr()` and `print_regs()` tapset functions. As mentioned before, BPFTrace provides register values through `reg()` function.

Here are some useful context information:

---
_Description_ | _DTrace_ | _SystemTap_ | _BPFTrace_
Current executing thread | `curthread` | `task_current()` | `curtask`
ID of current thread | `tid` | `tid()` | `tid`
ID of current process | `pid` | `pid()` | `pid`
ID of parent of current process | `ppid` | `ppid()` | -
User ID and group ID of current process | `uid`/`gid` | `uid()`/`gid()`, \
                                                        `euid()`, `egid()` | `uid` / `gid`
Name of current process executable | `execname` \
                                     `curpsinfo->ps_fname` | `execname()` | `comm`
Command Line Arguments | `curpsinfo->ps_psargs` | `cmdline_*()` | -
CPU number | `cpu` | `cpu()` | `cpu`
CGroup of current process | - | - | `cgroup`
Probe names | `probeprov`, `probemod`,     \
              `probefunc`, `probename`     \
            | `pp()`, `pn()`, `ppfunc()`,  \
              `probefunc()`, `probemod()`  \
            | `probe`, `func`
---

#### References

 * ![image:dtraceicon](icons/dtrace.png) [Built-in Variables](http://docs.oracle.com/cd/E19253-01/817-6223/chp-variables/index.html#6mlkidlfu)
 * ![image:stapset](icons/stapset.png) [Context Functions](https://sourceware.org/systemtap/tapsets/context_stp.html)
