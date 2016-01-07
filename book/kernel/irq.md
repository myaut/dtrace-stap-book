### Interrupt handling and deferred execution

Single instance of processor (core or hardware thread) can execute only single flow of instructions and won't switch to another flow of instructions unless it is explicitly specified with branch instruction. This model, however, prevents operating system from implementing illusion of multiprocessing by periodically switching active threads (which represent flow of instructions). To implement multiprocessing and many other concepts, processor provide mechanism of _interrupts_. 

When device, another processor or internal processor unit has to notify current processor about some event: arrival of data in ring buffer of NIC, process exit leading to killing all of its threads or integer division by zero, they send an _interrupt request (IRQ)_.  Multiprocessing itself is handled through virtual device, called _system timer_ which can send interrupt after pre-defined time. In response to interrupt request, processor saves context on current stack and switches its execution to pre-defined _interrupt service routine (ISR)_ or _interrupt handler_. The closest userspace analogue of interrupts is signals. 

Interrupts are generally considered bad for performance as their handling "steals" time from actual program, leads to cache cooldown, etc., so a lot of effort in operating system development is put to reduce their negative effect. It is done through better balancing interrupts across processors and deferring execution of the interrupt service routine. Due to that only high-priority interrupts such as _Non-Maskable Interrupt (NMI)_ are handled directly in a interrupt service routine. 

Most interrupts use _interrupt threads_ - separate threads that can handle interrupt but in a same time can be interrupted or de-scheduled (but they will have highest priorities in Solaris). These threads are created by device drivers in Linux and then saved into `handler` field of `irqaction` structure and are being activated if interrupt handler has returned `IRQ_WAKE_THREAD` code. In Solaris, on contrary, each processor has its own interrupt handling thread which is saved into `cpu_intr_thread` of `cpu_t`.

SystemTap provides irq tapset which contains probes for tracing interrupt handlers:

```
# stap --all-modules -e '
    probe irq_handler.entry, irq_handler.exit { 
        printf("%-16s %s irq %d dev %s\n", pn(), symname(handler), 
            irq, kernel_string(dev_name)); }  ' 
```

Solaris has several SDT probes that can be used to trace interrupt handlers too:

```
# dtrace -n '
    av_dispatch_autovect:entry { 
        self->vec = arg0; } 
    sdt:::interrupt* { 
        printf("%s irq %d dev %s", probename, self->vec, 
            (arg0) ? stringof(((struct dev_info*) arg0)->devi_addr) : "??");  
        sym(arg1);  } '
```

Interrupt threads is not the only method to defer execution of certain kernel code: kernel provides a lot of other facilities to do so. They are referred to as _bottom halves_ of interrupt, while interrupt handler itself is a _top half_ which responsibility is to activate bottom half. An example of them is defferred interrupt handlers __softirqs__ and __tasklets__ in Linux which are executed in the context of `ksoftirqd-N` kernel threads. They are prioritized where `TASKLET_SOFTIRQ` has the lesser priority and serves for execution of tasklets (they are more lightweight than softirqs). They could be traced using `softirq.entry` and `softirq.exit` probes.

If bottom half (or any other in-kernel job) has to be executed at specified moment of time, Linux provides __timers__ while Solaris has _cyclic subsystem_ which can be accessed through __callouts__ or `timeout()`/`untimeout()` calls.

To simplify execution of small chunks of work Linux provide __workqueue__ mechanism which has closest analogue in Solaris -- __task queues__. They provide a pool of worker threads whose extract function and data pointers from a queue and call that function. Many drivers may implement their own work queues. Solaris provides static probes to trace task queues:

```
# dtrace -n '
    taskq-exec-start, taskq-enqueue { 
        this->tqe = (taskq_ent_t*) arg1; 
        printf("%-16s %s ", probename, stringof(((taskq_t*) arg0)->tq_name)); 
        sym((uintptr_t) this->tqe->tqent_func); 
        printf("(%p)", this->tqe->tqent_arg); }'
```

SystemTap provide corresponding probes in irq tapset, but they do not work in modern kernels:

```
# stap --all-modules -e '
    probe workqueue.insert, workqueue.execute { 
        printf("%-16s %s %s(%p)\n", 
            pn(), task_execname(wq_thread), symname(work_func), work); 
    }  ' 
```

Linux kernel 2.6.36 got new workqueue implementation, and, eventually new set of tracepoints which can be traced like this (SystemTap >=2.5 required):

```
# stap --all-modules -e '
probe kernel.trace("workqueue_execute_end"),
      kernel.trace("workqueue_execute_start") {
        printf("%s %s(%p)\n", 
                pn(), symname($work->func), $work);  } ' 
```
