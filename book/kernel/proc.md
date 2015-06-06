### Process management

!!! DEF
According to Andrew Tanenbaum's book "Modern Operating Systems",

> All the runnable software on the computer, sometimes including the operating system, is organized into a number of sequential processes, or just _processes_ for short. A process is just an instance of an executing program, including the current values of the program counter, registers, and variables.

!!!

!!! INFO
Each process has its own address space -- in modern processors it is implemented as a set of pages which map virtual addresses to a physical memory. When another process has to be executed on CPU, _context switch_ occurs: after it processor special registers point to a new set of page tables, thus new virtual address space is used. Virtual address space also contains all binaries and libraries and saved process counter value, so another process will be executed after context switch. Processes may also have multiple _threads_. Each thread has independent state, including program counter and stack, thus threads may be executed in parallel, but they all threads share same address space.
!!!

#### Process tree in Linux

Processes and threads are implemented through universal `task_struct` structure (defined in `include/linux/sched.h`), so we will refer in our book as _tasks_. First thread in process is called _task group leader_ and all other threads are linked through list node `thread_node` list head and contain pointer `group_leader` which references `task_struct` of their process. Children processes refer to parent process through `parent` pointer and linked through `sibling` list node. Parent process linked with its children using `children` list head. 

![image:linux-task](linux/task.png)

Task which is currently executed on CPU is accessible through `current` macro which actually calls function to get task from run-queue of CPU where it is called. To get current pointer in SystemTap, use `task_current()`. You can also get pointer to a `task_struct` using `pid2task()` function which accepts PID as its first argument. Task tapset provides several functions similiar for functions used as [Probe Context][lang/context]. [task-funcs] They all get pointer to a `task_struct` as their argument:
	* `task_pid()` and `task_tid()` -- ID of the process ID (stored in `tgid` field) and thread (stored in `pid` field) respectively. Note that kernel most of the kernel code doesn't check cached `pid` and `tgid` but use namespace wrappers.
	* `task_parent()` -- returns pointer to a parent process, stored in `parent`/`real_parent` fields
	* `task_state()` -- returns state bitmask stored in `state`, such as `TASK_RUNNING` (0), `TASK_INTERRUPTIBLE` (1), `TASK_UNINTTERRUPTIBLE` (2). Last 2 values are for sleeping or waiting tasks -- the difference that only interruptible tasks may receive signals. 
	* `task_execname()` -- reads executable name from `comm` field, which stores base name of executable path. Note that `comm` respects symbolic links.
	* `task_cpu()` -- returns CPU to which task belongs

There are several other useful fields in `task_struct`:
	* `mm` (pointer to `struct mm_struct`) refers to a address space of a process. For example, `exe_file` (pointer to `struct file`) refers to executable file, while `arg_start` and `arg_end` are addresses of first and last byte of argv passed to a process respectively
	* `fs` (pointer to `struct fs_struct`) contains filesystem information: `path` contains working directory of a task, `root` contains root directory (alterable using `chroot` system call)
	* `start_time` and `real_start_time` (represented as `struct timespec` until 3.17, replaced with `u64` nanosecond timestamps) -- _monotonic_ and _real_ start time of a process.
	* `files` (pointer to `struct fs_struct`) contains table of files opened by process
	* `utime` and `stime` (`cputime_t`) contain amount of time spent by CPU in userspace and kernel respectively. They can be accessed through Task Time tapset.

Script `dumptask.stp` demonstrates how these fields may be useful to get information about current process.

````` scripts/stap/dumptask.stp

#### Process tree in Solaris

Solaris Kernel distinguishes threads and processes: on low level all threads represented by `kthread_t`, which are presented to userspace as _Light-Weight Processes_ (or _LWPs_) defined as `klwp_t`. One or multiple LWPs constitute a process `proc_t`. They all have references to each other, as shown on the following picture:

![image:sol-proc](solaris/proc.png)

Current thread is passed as `curthread` built-in variable to probes. Solaris `proc` provider has `lwpsinfo_t` and `psinfo_t` providers that extract useful information from corresponding thread, process and LWP structures.

---
3,1 __Process__
`psinfo_t` __field__ | `proc_t` __field__ | __Description__
`p_exec` |  | vnode of executable file
`p_as` | | process address space
`pr_pid` | In `p_pid` of type `struct pid` | Information about process ID
`pr_uid`, `pr_gid`, \
`pr_euid` `pr_egid` | In `p_cred` of type `struct cred` | User and group ID of a process
 | `p_stat` | Process state
`pr_dmodel` | `p_model` | Data model of a process (32- or 64- bits)
`pr_start` | `p_user.u_start`, `p_mstart` | Start time of process, from epoch
`pr_fname` | `p_user.u_comm` | Executable name
 | `p_user.p_cdir` | vnode of current process directory
 | `p_user.p_rdir` | vnode of root process directory
For current process -- `fds` pseudo-array | `p_user.u_finfo` | Open file table 
3,1 __Thread / LWP__
`lwpsinfo_t` __field__ | `kthread_t` __field__ | __Description__
`pr_lwpid` | `t_tid` | ID of thread/LWP
`pr_state` (enumeration) \
 or `pr_sname` (letter) | `t_state` |  State of the thread -- one of `SSLEEP` for sleeping, `SRUN` for runnable thread, `SONPROC` for thread that is currently on process, `SZOMB` for zombie threads, `SSTOP` for stopped threads and `SWAIT` for threads that are waiting to be runnable.
`pr_stype` | | If process is sleeping on synchronization object identifiable as _wait channel_ (`pr_wchan`), this field contains type of that object, i.e.: `SOBJ_MUTEX` for mutexes and `SOBJ_CV` for condition variables
| `t_mstate` | micro-state of thread (see also `prstat -m`)
---

Parent process has `p_child` pointer that refers to its first child, while list of children is doubly-linked list with `p_sibling` pointer (next) and `p_psibling` (previous) pointers. Each child contains `p_parent` pointer and `p_ppid` process ID which refers his parent. Threads of the process is also a doubly-linked list with `t_forw` (next) and `t_prev` pointers. Thread references corresponding LWP with `t_lwp` pointer and its process with `t_procp` pointer. LWP refers to a thread through `lwp_thread` pointer, and to a process through `lwp_procp` pointer. 

The following script dumps information about current thread and process. Because DTrace doesn't support loops and conditions, it can read only first 9 files and 9 arguments and does that by generating multiple probes with preprocessor. 

````` scripts/dtrace/dumptask.d

!!! WARN
`psinfo_t` provider features `pr_psargs` field that contains first 80 characters of process arguments. This script uses direct extraction of arguments only for demonstrational purposes and to be conformatnt with dumptask.stp. Like in SystemTap case, this approach doesn't allow to read non-current process arguments. 
!!!

#### Lifetime of a process

Lifetime of a process and corresponding probes are shown in the following image:

![image:forkproc](forkproc.png)

Unlike Windows, in Unix process is spawned in two stages:
 * Parent process calls `fork()` system call. Kernel create exact copy of a parent process including address space (which is available in copy-on-write mode) and open files, and gives it a new PID. If `fork()` was successful, it will return in the context of two processes (parent and child), with the same instruction pointer. Following code usually closes files in child, resets signals, etc. 
 * Child process calls `execve()` system call, which replaces address space of a process with a new one based on binary which is passed to `execve()` call. 
 
!!! WARN
There is a simpler call, `vfork()`, which will not cause copying of an address space, which will make it a bit more effecient. Linux features universal `clone()` call which allow to choose which features of a process should be cloned, but in the end, all these calls are wrappers for `do_fork()` function.
!!!
 
When child process finishes its job, it will call `exit()` system call. However, process may be killed by a kernel due to incorrect condition (like triggering kernel oops) or machine fault. If parent wants to wait until child process finishes, it will call `wait()` system call (or `waitid()` and similiar calls), which will stop parent from executing until child exits.
`wait()` call also receive process exit code, so only after that corresponding `task_struct` will be destroyed. If no process waited on a child, and child is exited, it will be treated as _zombie_ process. Parent process may be also notified by kernel with `SIGCHLD` signal.

Processes may be traced with kprocess and scheduler tapsets in SystemTap, or DTrace proc provider. System calls may be traced with appropriate probes too. Here are some useful probes:

---
__Action__ | __DTrace__ | __SystemTap__
Process creation | `proc:::create` | \
									 * `kprocess.create` \
									 * `scheduler.process_fork`
Forked process begins its execution | \
	* `proc:::start` -- called in new process context | \
		* `kprocess.start` -- called in a new process context \
		* `scheduler.wakeup_new` -- process has been dispatched onto CPU first time
`execve()` | \
	* `proc:::exec` -- entering `execve()` \
	* `proc:::exec-success` -- `execve()` finished successfully \
	* `proc:::exec-failure` -- `execve()` has failed, \
		`args[0]` contains errno | \
			* `kprocess.exec` -- entering `execve()` \
			* `kprocess.exec_complete` -- `execve()` has been completed, \
			`success` variable has true-value if completed successfully, \
			`errno` variable has error number in case of error
Process finished | \
	* `process::exit` -- process exited normally via `exit()` syscall \
	* `process::fault` -- process has been terminated due to fault | \
		* `kprocess.exit` \
		* `scheduler.process_exit`
Process structures deallocated due to `wait()`/`SIGCHLD` | \
	- | \
	* `kprocess.release` \
	* `scheduler.process_free` 
LWP management | \
	* `proc:::lwp-create` \
	* `proc:::lwp-start` \
	* `proc:::lwp-exit` | \
		LWPs are not supported in Linux
---

These probes are demonstrated in the following scripts. 

````` scripts/stap/proc.stp

Running this script for `uname` program called in foreground of `bash` shell gives following output:
```
2578[    bash]/  2576[    sshd] syscall.fork
2578[    bash]/  2576[    sshd] kprocess.create
2578[    bash]/  2576[    sshd] scheduler.process_fork
	PID: 2578 -> 3342
2578[    bash]/  2576[    sshd] scheduler.wakeup_new
3342[    bash]/  2578[    bash] kprocess.start
2578[    bash]/  2576[    sshd] syscall.wait4
2578[    bash]/  2576[    sshd] scheduler.process_wait
	filename: /bin/uname
3342[    bash]/  2578[    bash] kprocess.exec
3342[    bash]/  2578[    bash] syscall.execve
3342[   uname]/  2578[    bash] kprocess.exec_complete
	return code: 0
3342[   uname]/  2578[    bash] kprocess.exit
3342[   uname]/  2578[    bash] syscall.exit
3342[   uname]/  2578[    bash] scheduler.process_exit
2578[    bash]/  2576[    sshd] kprocess.release
```

````` scripts/dtrace/proc.d

DTrace will give similiar outputs, but also will reveal LWP creation/destruction:

```
 16729[    bash]/ 16728[    sshd] syscall::forksys:entry
 16729[    bash]/ 16728[    sshd] proc::lwp_create:lwp-create
 16729[    bash]/ 16728[    sshd] proc::cfork:create
        PID: 16729 -> 17156
 16729[    bash]/ 16728[    sshd] syscall::waitsys:entry
 17156[    bash]/ 16729[    bash] proc::lwp_rtt_initial:start
 17156[    bash]/ 16729[    bash] proc::lwp_rtt_initial:lwp-start
 17156[    bash]/ 16729[    bash] syscall::exece:entry
 17156[    bash]/ 16729[    bash] proc::exec_common:exec
        filename: /usr/sbin/uname
 17156[   uname]/ 16729[    bash] proc::exec_common:exec-success
 17156[   uname]/ 16729[    bash] proc::proc_exit:lwp-exit
 17156[   uname]/ 16729[    bash] proc::proc_exit:exit
        return code: 1
     0[   sched]/     0[     ???] proc::sigtoproc:signal-send
```

#### References

* ![image:stapset](icons/stapset.png) [Context Functions](https://sourceware.org/systemtap/tapsets/context_stp.html)
* ![image:stapset](icons/stapset.png) [Task Time Tapset](https://sourceware.org/systemtap/tapsets/task_time_stp.html)
* ![image:stapset](icons/stapset.png) [Kernel Process Tapset](https://sourceware.org/systemtap/tapsets/kprocess.stp.html)
* ![image:stapset](icons/stapset.png) [Scheduler Tapset](https://sourceware.org/systemtap/tapsets/sched.stp.html)
* ![image:dtraceicon](icons/dtrace.png) [proc Provider](http://docs.oracle.com/cd/E19253-01/817-6223/chp-proc/index.html)