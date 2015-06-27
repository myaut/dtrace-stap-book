### Process scheduler

!!! DEF
Process _scheduler_ is a key component of modern multitasking operating systems which distributes processor time between several tasks. Because time periods allocated to programs is relatively small to be noticed by human (milliseconds), that creates an illusion of parallel execution or _concurrent_ execution. 
!!!

!!! DEF
When scheduler desides that one task should leave CPU to run another one, scheduler calls a _dispatcher_ that performs a _context switch_. Context switch changes `current`/`curthread` pointer so when mode switched back to userspace, new task will be picked with appropriate address space and registers values. If context switches are rare, that can cause task _starvation_ and user can notice that system become unresponsive, of context switches are too often, TLB will be cleared too often, caches will be cold, so performance will degrade, so picking an optimal _timeslice_ allocated to a task is a hard choice.
!!!

In Solaris functions of the scheduler is invoked through `swtch()` function, in Linux through `schedule()` functions and set of derivatives like `cond_resched()`. 

Process lifetime in terms of the scheduler is shown on the following picture.

![image:sched](sched.png)

In scheduler, context switching may be split in two steps:

 * Current task leaves CPU. This event is traceable as `sched:::off-cpu` in DTrace or `scheduler.cpu_off` in SystemTap. This may be caused by many reasons:
    * Task was blocked on kernel synchronisation object **(6)**, for example due to call to `poll()` and waiting network data. In this case task is put into _sleep queue_ related to that synchronisation object. It would later be unblocked by another task **(7)**, thus being put back to run-queue. 
    * Task is voluntary gives control to a scheduler by calling `yield()` call **(3)**
    * Task has been exhausted its timeslice or task with higher priority has been added to a run queue (or a new, forked process added to queue), which is called _preemptiveness_. Usually timeslice is checked by system timer, which is traceable as `sched:::tick` probe in DTrace or `scheduler.tick`. **(3)** Some system calls and interrupts may also trigger context switch. 
 * New task is picked to be run on CPU **(2)**. When CPU resumes from kernel mode, interrupt or system call, it changes context to a new task, like in `resume()` low-level routine of Solaris. 
Context switch may be traced in SystemTap with `scheduler.ctxswitch` probe.

OS creates at least one run-queue per CPU in SMP systems. When some CPU prepares to become idle, it may check run-queues of other CPUs and _steal_ task from it, thus task _migrates_ **(5)** between CPUs. This  allows to balance tasks across CPUs, but other factors like NUMA locality of process memory, cache hotness should be taken into account. Migration may be tracked by with `scheduler.migrate` probe in SystemTap. DTrace doesn't provide special probe for that, but it may be tracked comparing CPU ids in `on-cpu` and `off-cpu` probes:

```
# dtrace -n '
	sched:::off-cpu {
		self->cpu = cpu; }
	sched:::on-cpu 
	/self->cpu != cpu/
	{
		/* Migration */	} '
```

Usually task is blocked on various synchronisation objects waiting for data available for processing, i.e. `accept()` will block until client will connect and `recv()` will block until client will send new data. There is no need to use a processor when no data is available, so task simply leaves CPU and being put to a special _sleep queue_ related to that object. Speaking of `accept()` call, it would be `so_acceptq_cv` condition variable in kernel socket object (`sonode`) in Solaris and `sk_wq` wait queue wrapper in Linux object `sock`. We will cover synchronisation objects in detail later in section [Synchronisation objects][kernel/sobj].

Solaris has dedicated probes for sleeping and awoken processes: `sched:::sleep` and `sched:::wakeup` correspondingly which may be used like this:
```
# dtrace -n '
	sched:::sleep { 
		printf("%s[%d] sleeping", execname, pid); 
	} 
	sched:::wakeup { 
		printf("%s[%d] wakes up %s[%d]", execname, pid, 
			args[1]->pr_fname, args[1]->pr_pid); }' | grep cat
```

Note that wakeup process is called in context of process which initiates task unblocking. 

SystemTap provides `scheduler.wakeup` probe for process that return to a run-queue, but has no special probe for sleeping process. The most correct way to do that is to trace `schedule()`  calls and task state transitions: task should change its state from `TASK_RUNNING` to a `TASK_INTERRUPTIBLE` or `TASK_UNINTERRUPTIBLE`. In following example, however, we will use much simpler approach: most sleep queues are implemented as _wait queues_ in Linux, so we will trace corresponding call, `add_wait_queue()` that puts task onto queue:
```
# stap -e '
	probe kernel.function("add_wait_queue") { 
		printf("%s[%d] sleeping\n", execname(), pid()); 
	} 
	probe scheduler.wakeup { 
		printf("%s[%d] wakes up %s[%d]\n", execname(), pid(),
			pid2execname(task_pid), task_pid); }' | grep cat
```

These examples may be tested with the following simple one-liner:
```
# bash -c 'while : ; do echo e ; sleep 0.5 ; done ' | cat
```

When dispatcher puts task onto queue, it is called _enqueuing_ **(4)**, when it removes it from queue, it is called _dequeuing_ **(1)**. DTrace has probes `sched:::enqueue` and `sched:::dequeue`. SystemTap doesn't have these probes, but you may trace `enqueue_task()` and `dequeue_task()` for that.

As we mentioned before, purpose of the scheduler is to distribute time between tasks. To do that, it prioritizes tasks, so to pick a task for execution it may create multiple queues (one for each priority level), than walk over these queues and pick _first_ task with top-level priority. Such approach is called _cyclic planning_. _Fair planning_, on contrary, is concerned about time consumption by difference threads, processes, users and even services (which are all considered as _scheduling entities)_, and try to balance available processor time fairly. 

#### Scheduling in Solaris

Solaris implements cyclic scheduling, but it support fair scheduling algorithms via FSS (_fair share scheduling_) class. Each thread in Solaris may have priority from 0 to 170 which is saved in `t_pri` field of `kthread_t`. Each thread has its own scheduler class, which may have different algorithms for allocating timeslices, prioritizing threads. Generic API for scheduler class is provided as `t_clfuncs` field of thread where each field is a pointer to a corresponding function, while specific scheduler data is kept under `t_cldata` field. 

The following table shows scheduler classes implemented in Solaris.

---
__Class__ | __Priority range__ | __Description__
 - | 160-169 | Interrupt threads (they are not handled by scheduler explicitly)
RT | 100-159 | _RealTime_ processes and threads
SYS | 60-99 | _SYStem_ -- for kernel threads which always have precedence over user processes. Also, timeslices are allocated to them, they consume as much processor time as they can
SYSDC | 0-99 | _SYStem Duty Cycles_ -- for CPU-bound kernel threads like ZFS pipeline (which involves encryption and compression). This class is implemented to prevent userspace starvation under heavy I/O load.
TS and IA | 0-59 | _Time Sharing_ and _InterActive_ -- default classes for userspace processes. TS class has dynamic priorities: if thread had consumed entire timeslice, its priority is reduced to give room to other threads. IA is a modification of TS class which also adds small "boost" (usually, 10 priorities) for processes which have focused window (useful for graphics stations)
FX | 0-59 | _FiXed_ -- unlike TS/IA, such processes never change their priorities unless it is done by user themself
FSS | 0-59 | _Fair Share Scheduler_ -- allows to distribute processor time proportionally between groups of processes such as zones or projects
---

Solaris dispatcher control structures are shown on the following picture:

![image:sol-sched](solaris/sched.png)

Each processor has corresponding `cpu_t` structure, which includes two pointers to threads: `cpu_dispthread` -- a thread chosen by scheduler to be the next process after resume, and `cpu_thread` -- process whcih is currently is on CPU. `cpu_last_swtch` contains time of last context switch in lbolts (changed into high-resolution time in nanoseconds in Solaris 11). Each `cpu_t` has dispatcher queue represented by `disp_t` structure and corresponding array of queue heads of type `dispq_t`. Each queue head has links to first and last thread in queue (`kthread_t` objects are linked through `t_link` pointer) and `dq_sruncnt` -- number of threads in this queue. 

`disp_t` refers queues through `disp_q` pointer which refers first queue with priority 0 and `disp_q_limit` which points one entry beyound array of dispatcher queues. `disp_qactmap` contains bitmap of queues that have active processes at the moment. `disp_npri` is the number of priorities serviced by this dispatcher object -- it should be 160. `disp_maxrunpri` contains maximum priority of a thread in this dispatcher object -- it will be top-most queue which has active processes and when thread will be switched, this queue will be checked first. `disp_max_unbound_pri` also contains maximum priority of a thread, but only for a thread that is not bound to a corresponding processor and thus may be considered a candidate for task-stealing by free CPUs. Finally, `disp_nrunnable` has total number of runnable threads which is serviced by this dispatcher object. 

!!! WARN
Newer Solaris 11 versions use `hrtime_t` type for `cpu_last_swtch` (high-resolution unscaled time).
!!!

By default Solaris userspace processes use TS scheduler, so let look into it. Key parameter that used in it is `ts_timeleft` which keeps remaining thread timeslice. Initial value of `ts_timeleft` is taken from table `ts_dptbl` from field `ts_quantum`. Each row in that table matches priority level, so processes with lower priorities will have larger quantums (because they will get CPU rarely). You can check that table and override its values with dispadmin command, for example:
```
# dispadmin -c TS -g
```
Priority is also set dynamically in TS scheduler: if thread will exhaust its timeslice, its priority will be lowered according to `ts_tqexp` field, and if it will be awaken after sleep, it will get `ts_slpret` priority. Modern Solaris systems were replaced `ts_timeleft` with `ts_timer` (for non-kernel threads those have `TSKPRI` flag is set).

Tracer for TS scheduler is available in the following listing:

````` scripts/dtrace/tstrace.d

Let's demonstrate some of TS features live. To do that we will conduct two TSLoad experiments: _duality_ and _concurrency_. In first experiment, _duality_ we will create two different types of threads: _workers_ which will occupy all available processor resources, and _manager_ which will rarely wakeup (i.e. to queue some work possibly and report to user), so _manager_ should be immideately dispatched. In our example manager had LWPID=7 while worker had LWPID=5. Experiment configuration is shown in the following file:

````` experiments/duality/experiment.json

Here is sample output for _duality_ experiment (some output was omitted):

```
=> <b>cv_unsleep</b> [wakeup] 
        CPU : last switch: T-50073us rr: 0 kprr: 0
        wakeup t: ffffc100054f13e0 tsexperiment[1422]/7 TS pri: 59        
=> <b>setbackdq</b>
        setbackdq t: ffffc100054f13e0 tsexperiment[1422]/7 TS pri: 59        
=> <b>setfrontdq</b>
        setfrontdq t: ffffc10005e90ba0 tsexperiment[1422]/5 TS pri: 0        
=> <b>disp</b>
        CPU : last switch: T-50140us rr: 1 kprr: 0
                current t: ffffc10005e90ba0 tsexperiment[1422]/5 TS pri: 0
                disp    t: ffffc10005e90ba0 tsexperiment[1422]/5 TS pri: 0
        DISP: nrun: 2 npri: 170 max: 59(65535)
        curthread:  t: ffffc10005e90ba0 tsexperiment[1422]/5 TS pri: 0
        TS: timeleft: 19 flags:  cpupri: 0 upri: 0 boost: 0 => 0
        disp t: ffffc100054f13e0 tsexperiment[1422]/7 TS pri: 59
        TS: timeleft: 3 flags:  cpupri: 59 upri: 0 boost: 0 => 0
=> <b>disp</b>
        CPU : last switch: T-1804us rr: 0 kprr: 0
                current t: ffffc100054f13e0 tsexperiment[1422]/7 TS pri: 59
                disp    t: ffffc100054f13e0 tsexperiment[1422]/7 TS pri: 59
        DISP: nrun: 1 npri: 170 max: 0(65535)
        curthread:  t: ffffc100054f13e0 tsexperiment[1422]/7 TS pri: 59
        disp t: ffffc10005e90ba0 tsexperiment[1422]/5 TS pri: 0  
```

Note that when manager wokes up, it has maximum priority: 59 but being put to the queue tail. After that worker thread is being queued because `cpu_runrun` flag is being set (note `rr` change), number of runnable processes increases up to two. After 1.8 ms manager surrenders from CPU, and worker regains control of it.

In _concurrency_ experiment, on the opposite we will have two threads with equal rights: they both will occupy as much CPU as they can get thus being _worker_ processes. Experiment configuration is shown in the following file:

````` experiments/concurrency/experiment.json

Here is sample output for _concurrency_ experiment (some output was omitted):

```
=> <b>disp</b> 
        CPU : last switch: T-39971us rr: 1 kprr: 0
                current t: ffffc10009711800 tsexperiment[1391]/6 TS pri: 40
                disp    t: ffffc10009711800 tsexperiment[1391]/6 TS pri: 40
        DISP: nrun: 2 npri: 170 max: 40(65535)
        curthread:  t: ffffc10009711800 tsexperiment[1391]/6 TS pri: 40
        TS: timeleft: 4 flags:  cpupri: 40 upri: 0 boost: 0 => 0
        disp t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 40
        TS: timeleft: 4 flags:  cpupri: 40 upri: 0 boost: 0 => 0
=> <b>clock_tick </b>
        clock_tick t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 40
        TS: timeleft: 3 flags:  cpupri: 40 upri: 0 boost: 0 => 0
=> <b>clock_tick   </b>      
        clock_tick t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 40
        TS: timeleft: 2 flags:  cpupri: 40 upri: 0 boost: 0 => 0
=> <b>clock_tick</b>         
        clock_tick t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 40
        TS: timeleft: 1 flags:  cpupri: 40 upri: 0 boost: 0 => 0
        cpu_surrender t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 30
=> <b>clock_tick</b>         
        clock_tick t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 30
        TS: timeleft: 0 flags: TSBACKQ| cpupri: 30 upri: 0 boost: 0 => 0
=> <b>setbackdq </b>
        setbackdq t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 30
        TS: timeleft: 8 flags:  cpupri: 30 upri: 0 boost: 0 => 0
=> <b>disp  </b>      
        curthread:  t: ffffc10005c07420 tsexperiment[1391]/5 TS pri: 30
        TS: timeleft: 8 flags:  cpupri: 30 upri: 0 boost: 0 => 0
        disp t: fffffffc80389c00 sched[0]/0 SYS pri: 60
=> <b>disp </b>
        curthread:  t: fffffffc80389c00 sched[0]/0 SYS pri: 60
        disp t: ffffc10009711800 tsexperiment[1391]/6 TS pri: 40
        TS: timeleft: 4 flags:  cpupri: 40 upri: 0 boost: 0 => 0
```

Note how `timeleft` field is changing: it is calculated as `ts_timer` - `ts_lwp->lwp_ac.ac_clock`. After each clock tick latter is incremented thus timeleft is decrementing. When timeleft becomes 0, it means that _worker_ has exhausted scheduler quantum, so its priority falls from 40 to 30 and it is being put to the tail of corresponding dispatcher queue. After that `sched` thread runs for a short time (which is some kernel thread managed by SYS scheduler), and eventually another _worker_ thread gets on CPU.

#### Scheduling in Linux

Cyclic scheduling was implemented in Linux O(1) scheduler, but it was replaced with Completely Fair Scheduler (CFS) scheduler in 2.6.22 kernel. Cyclic scheduling is represented by RT class which is rarely used. There are also some non-default schedulers like BFS which are not available in vanilla kernel but shipped as separate patches. Each `task_struct` has field `policy` which determines which scheduler class will be used for it. Policies are shown in the following table:

---
__Priority__ | __Class__ | __Policy__ | __Description__
1 | stop | - | Special class for stopped CPUs. Such CPUs cannot execute any threads.
1,2 2 |1,2 rt | `SCHED_RR` |1,2 Implements cyclic scheduling using round-robin or FIFO policies
			    `SCHED_FIFO`
1,2 3 |1,2 fair (CFS) | `SCHED_NORMAL` (`SCHED_OTHER`) | Default policy for most kernel and user threads 
                        `SCHED_BATCH` | Similiar to `SCHED_NORMAL`, but process which was recently waken up won't try to dispatch on CPU which is more fittful for batch tasks
4 | idle | `SCHED_IDLE` | Idle threads -- picked only when other classes do not have runnbalbe threads.
---

!!! INFO
Consider the following situation: there are currently two users on a 8-CPU host where user dima had run `make -j8` and another user, say myaut, had run `make -j4`. To maintain fairness so users dima and myaut will get equal amount of CPU time, you will need renice processes of user dima, but calculating correct correct priority penalty will be inobvious. Instead, you can create a two CGroups and add one instance of make per CGroup. Than all tasks which are spawned by dima's `make` will be accounted in scheduler entity corresponding to dima's CGroup.
!!!

Let's look into details of implementaion of CFS scheduler. First of all, it doesn't deal with tasks directly, but schedules _scheduler entities_ of type `struct sched_entity`. Such entity may represent a task or a queue of entities of type `struct cfs_rq` (which is referenced by field `my_q`), thus allowing to build hierarchies of entities and allocate resources to task groups which are called _CGroups_ in Linux. Processor run queue is represented by type `struct rq` contains field `cfs` which is instance of `struct cfs_rq` and contains queue of all high-level entities. Each entity has `cfs_rq` pointer which points to CFS runqueue to which that entity belongs:

![image:cfs-sched](linux/sched.png)

In this example processor run queue has two scheduler entities: one CFS queue with single task (which refers top-level `cfs_rq` through `parent` pointer) in it and one top-level task. 

CFS doesn't allocate timeslices like TS scheduler from Solaris did. Instead it accounts total time which task had spend on CPU and saves it to `sum_exec_runtime` field. When task is dispatched onto CPU, its `sum_exec_runtime` saved into `prev_sum_exec_runtime`, so calculating their difference will give time period that task spent on CPU since last dispatch. `sum_exec_runtime` is expressed in nanoseconds but it is not directly used to measure task's runtime. To implement priorities, CFS uses task weight (in field `load.weight`) and divides runtime by tasks weight, so tasks with higher weights will advance their runtime meter (saved into `vruntime` field) slower. Tasks are sorted according their `vruntime` in a red-black tree called `tasks_timeline`, while left-most task which has lowest `vruntime` of all tasks and saved into `rb_leftmost`. 

CFS has special case for tasks that have been woken up. Because they can be sleeping too long, their `vruntime` may be too low and they will get unfairly high amount of CPU time. To prevent this, CFS keeps minimum possible `vruntime` of all tasks in `min_vruntime` field, so all waking up tasks will get `min_vruntime` minus a predefined "timeslice" value. CFS also have a _scheduler buddies_ -- helper pointers for a dispatcher: `next` -- task that was recently awoken, `last` -- task that recently was evicted from CPU and `skip` -- task that called `sched_yield()` giving CPU to other entities.

So, let's implement a tracer for CFS scheduler:

````` scripts/stap/cfstrace.stp

Let's conduct same experiments we performed on Solaris. In "duality" experiment _manager_ task (TID=6063) didn't preempt _worker_ (TID=6061) immideately, but it was put into task_timeline tree. Since it would have minimum vruntime of all tasks there (note that CFS scheduler removes task from queue when it is dispatched onto CPU), it becomes left-most task. It picked on a next system tick:

```
=> <b>check_preempt_wakeup</b>:
    se:    curr tsexperiment/6061 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+-978205 vruntime: MIN+0
    se:      se tsexperiment/6063 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+41023325 vruntime: MIN+-6000000
    CFS_RQ: /
        nr_running: 2 load.weight: 2048 min_vruntime: 314380161884
        runnable_load_avg: 1067 blocked_load_avg: 0 
    se:   first tsexperiment/6063 SCHED_NORMAL
    se:     rb: tsexperiment/6063 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+41023325 vruntime: MIN+-6000000
<= <b>check_preempt_wakeup</b>

=> <b>task_tick_fair</b> J=4302675615 queued: 0 curr: tsexperiment/6061 SCHED_NORMAL
    sched_slice: 6000000
    se:    curr tsexperiment/6061 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+-260001 vruntime: MIN+260001
        delta_exec: 42261531        delta: 6260001
<= <b>task_tick_fair</b>

=> <b>pick_next_task_fair</b> D=42422710 J=4302675615
    pick_next_entity
    CFS_RQ: /
        nr_running: 2 load.weight: 2048 min_vruntime: 314380161884
        runnable_load_avg: 1067 blocked_load_avg: 0 
    se:   first tsexperiment/6063 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+42261531 vruntime: MIN+-6000000
    se:     rb: tsexperiment/6063 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+42261531 vruntime: MIN+-6000000
    se:   rb-r: tsexperiment/6061 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+-131878 vruntime: MIN+391879
<= <b>pick_next_task_fair</b>
    se:   sched tsexperiment/6063 SCHED_NORMAL
```

In _concurrency_ experiment thread receives 6ms timeslice (return value of `sched_slice()` function), so it will be executed until its `vruntime` won't exceed `min_vruntime`:

```
=> <b>pick_next_task_fair</b> D=7015045 J=4302974601
<= <b>pick_next_task_fair</b>
    se:   sched t: 0xffff880015ba0000 tsexperiment/6304 SCHED_NORMAL

=> <b>task_tick_fair</b> J=4302974602 queued: 0 curr: t: 0xffff880015ba0000 tsexperiment/6304 SCHED_NORMAL
    sched_slice: 6000000
    se:    curr tsexperiment/6304 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+-868810 vruntime: MIN+0
        delta_exec: 868810      delta: -4996961
<= <b>task_tick_fair</b>

...

=> <b>task_tick_fair</b> J=4302974608 queued: 0 curr: t: 0xffff880015ba0000 tsexperiment/6304 SCHED_NORMAL
    sched_slice: 6000000
    se:    curr tsexperiment/6304 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+-1007610 vruntime: MIN+1008440
        delta_exec: 6874211     delta: 1008440
<= <b>task_tick_fair</b>

=> <b>pick_next_task_fair</b> D=7040772 J=4302974608
    pick_next_entity
    CFS_RQ: /
        nr_running: 2 load.weight: 2048 min_vruntime: 337102568062
        runnable_load_avg: 2046 blocked_load_avg: 0 
    se:   first tsexperiment/6305 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+6874211 vruntime: MIN+0
    se:     rb: tsexperiment/6305 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+6874211 vruntime: MIN+0
    se:   rb-r: tsexperiment/6304 SCHED_NORMAL
        load.weight: 1024 exec_start: RQ+-160403 vruntime: MIN+1168843
<= <b>pick_next_task_fair</b>
    se:   sched tsexperiment/6305 SCHED_NORMAL
```

You can conduct these experiment on your own.