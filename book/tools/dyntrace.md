### Dynamic tracing

Unlike other approaches, dynamic tracing tool embeds tracing code into working user program or kernel, without need of recompilation or reboot. Since any processor instruction may be patched, it can virtually access any information you need at any place. 

Solaris DTrace development was begun in 1999, and it became part of Solaris 10 release. Along with other revolutionary Solaris 10 features, it shaken world of operating systems, and still evolve. You may found more information about DTrace history here: [Happy 5th Birthday, DTrace!](https://blogs.oracle.com/bmc/entry/happy_5th_birthday_dtrace).

Here are some DTrace information sources:
 * [Oracle Wiki](https://wikis.oracle.com/display/DTrace/DTrace)
 * [DTrace at SolarisInternals wiki](http://www.solarisinternals.com/wiki/index.php/DTrace_Topics)
 * «Solaris Performance and Tools» book
 * «DTrace - Dynamic Tracing in Oracle Solaris, Mac OS X and FreeBSD» book
 * [Solaris Dynamic Tracing Guide](http://download.oracle.com/docs/cd/E19253-01/817-6223/)
 
During course we will refer to _Solaris Dynamic Tracing Guide_ with the following sign: ![image:dtraceicon](icons/dtrace.png)

DTrace was open-sourced as a part of OpenSolaris, but due to license incompatibility, it can't be merged with Linux Kernel. Several ports existed, but they lacked of proper support. The only stable port is provided in Unbreakable Enterprise Kernel by Oracle for their own Linux distribution which is not wide-spread. There were attempt to develop another clone of DTrace -- DProbes, but it was a failure. Over time three major Linux players: Red Hat, Hitachi, IBM presented dynamic tracing system for Linux called [SystemTap](http://sourceware.org/systemtap/). It has two primary sources of information: [SystemTap Language Reference](http://sourceware.org/systemtap/langref/) to which we will reference with icon ![image:staplang](icons/staplang.png) [SystemTap Tapset Reference Manual](http://sourceware.org/systemtap/tapsets/) to which we will reference with icon ![image:stapset](icons/stapset.png). Of course, there is a Unix manual pages, to which we will refer with icon ![image:manpage](icons/manpage.png). 

SystemTap has to generate native module for each script it runs, which is huge performance penalty, so as alternative to it, [Ktap](https://github.com/ktap/ktap) is developing. Its language syntax shares some features with SystemTap, but it uses Lua and LuaJIT internally which makes it faster than SystemTap. Modern kernel versions have eBPF integrated -- they use BPF as a platform as in-kernel virtual machine (which provides both safety and stability guarantees, and quite fast), with extensions (hence, `e` in name) which provide map and output capabilities. Unfortunately, for a long time, BPF required C programming, even though wrappers, such as [BCC](https://github.com/iovisor/bcc) existed. SystemTap currently supports eBPF as tracing backend, but we will study BPF using [BPFTrace](https://github.com/iovisor/bpftrace) tool. While it may lack maturity, it seems to have a bright future. 

Finally, there is a [sysdig](http://www.sysdig.org/) which is scriptless. Another implementation of Linux tracing is [LTTng](http://lttng.org/). It had used static tracing and required kernel recompilation until version 2.0, but currently utilizes `ftrace` and `kprobe` subsystems in Linux kernel. As name of the book states, it describes SystemTap and BPFTrace for Linux and DTrace for Solaris.

[__index__:dynamic tracing] [__index__:consumer] [__index__:buffer]
Here are the workflow of dynamic tracing systems:

![image:dyntrace](dyntrace.png)

Dynamic tracing system logic is quite simple: you create a script in C-like language which is translated to a probe code by a _compiler_. DTrace scripts are written in D (do not disambiguate with D language from digital mars) have extension `.d`, while SystemTap scripts have extension `.stp` and written in SystemTap Language (it doesn't have special name). BPFTrace doesn't have special language name too (but it is very similar to D), and its scripts are usually ended with `.bt`. 

That _probe code_ is loaded into kernel address space by a kernel module and patches current binary code of kernel. Probes are writing collected data to intermediate _buffers_ that are usually lock-free, so they have small effect on kernels performance and doesn't need to switch context to a tracing program. Separate entity called _consumer_ reads that buffers and writes gathered data into terminal, pipe or to a file.
