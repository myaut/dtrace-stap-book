### Operating System Kernel

!!! DEF
According to Wikipedia, [Operating System Kernel](http://en.wikipedia.org/wiki/Kernel_%28operating_system%29) is

> a computer program that manages I/O (input/output) requests from software, and translates them into data processing instructions for the central processing unit and other electron components of a computer. The kernel is a fundamental part of a modern computer's operating system.

!!!

We will refer to operating system kernel as _kernel_ in the rest of the book. To access various kernel functions applications are using _system call_ mechanism, and by doing that they transfer control to kernel routines. The current state of application including all variables and current _program counter_ is called _context_. C is a programming language which is vastly used for writing Unix-like operating systems kernels such as Solaris, FreeBSD and Linux. C supports only procedural programming, but kernel developers adopted object-oriented and even functional programming. 

Where can we get information on kernel? Like I said, the most reliable source of such information is source codes which contain comments. You can use cross-reference tools to navigate source codes as easy as click a hyperlink. Some of them are publicly available: like [lxr.linux.no](http://lxr.linux.no/) which contains Linux source and [src.illumos.org](http://src.illumos.org/) which contains sources for Illimos (FOSS fork of OpenSolaris) in project illumos-gate. You can create your own cross-reference with OpenGrok tool: [https://github.com/OpenGrok/OpenGrok](https://github.com/OpenGrok/OpenGrok).

Of course we have to mention textual sources of information. For Linux it is:

  * `Documentation/` directory in kernel sources
  * [Linux Kernel Mailing List](http://lkml.org/)
  * [Linux info from source](http://lwn.net/)
  * Robert Love book "Linux Kernel Development"
  * [Linux Device Drivers Book](https://lwn.net/Kernel/LDD3/)
  
Some sources about Solaris:

  * [solaris.java.net](http://solaris.java.net/) -- remnants of old OpenSolaris site
  * Richard McDougall and Jim Mauro book "Solaris(TM) Internals: Solaris 10 and OpenSolaris Kernel Architecture"
  * Oracle course "Solaris 10 Operating System Internals"
  
!!! WARN
Solaris sources was closed after Oracle buyed Sun in 2009 and some information on Solaris become outdated.
!!!
