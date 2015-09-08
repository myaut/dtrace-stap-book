### Exercise 3

#### Part 1

In the first part of this exercise we will need to check which fields of `struct task_struct` in Linux or `proc_t` are responsible for which aspects of process functioning. You will need to apply following changes to dump task scripts: timer probe has to be replaced to a pair of probes: `proc:::exec-*` and `proc:::exit` in DTrace or `kprocess.exec_complete`  and `kprocess.exit` in SystemTap. We have used exit probes for `execve()` system call to collect command line arguments: they are not filled in unless `execve()` call finishes. 

Here list of expected observations during this exercise:

   * When you run program with extra argument, it will be cleared in `main()` function, so you will see original argument in exec-probe, but only 'X' letters when program exits.
   * When you run program through symbolic link `lab3-1`, VFS node which refer to a binary file will point to a regular file `lab3`. That node is represented by `p_exec` field of `proc_t` in Solaris or `exe_file` of `task_struct` in Linux. `execname`, however, will behave differently in Solaris and Linux. 
   * When you run program in chroot environment, root process directory will change from `/` to `/tmp/chroot`.
   
Here are resulting scripts (they are not much different from original):

````` scripts/stap/dumptask-lab3.stp
````` scripts/dtrace/dumptask-lab3.d

#### Part 2

First of all we have to create several associative arrays which will use PID as a key (we can't use thread-local variables here because `exit()` can be called from any of process threads), and timestamp as a value. Final data will be kept in aggregations which we already learned in exercise 2. 

We will use probes from the section _Lifetime of a process_. They are shown in the following picture:

![image:forkproc](forkproc.png)

However, we do not know PID at the time `fork()` is called so we will use thread-local variable for that. We can check return value of `fork()` in return probe and re-use timestamp saved previously if everything went fine and `fork()` has returned value greater than 1 or throw it away.

We wrote an ugly function `task_args()` to collect process arguments in `dumptask.stp` script. This data is available since SystemTap 2.5: `kprocess.exec` probe provides program's arguments in `argstr` argument. We will use `curpsinfo->pr_psargs` on Solaris as it keeps first 80 characters of command line to get rid of copying userspace arguments too. We will use `timestamp` variable in DTrace as a source of timestamps (again, a tautology). We will use `local_clock_us()` function as we do not care about CPU time skew. 

Finally, to reduce memory footprint in SystemTap, we will reduce associative arrays sizes. Here are resulting scripts:

````` scripts/stap/forktime.stp
````` scripts/dtrace/forktime.d

