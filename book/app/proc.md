### Userspace process tracing

We had covered kernel organization in detail in previous chapter, but it would be useless without userspace application that services end-user requests. It can be either simple `cat` program which we used in many previous examples to complex web application which uses web server and relational database. Like with the kernel, DTrace and SystemTap allow to set a probe to any instruction in it, however it will require additional switch to kernel space to execute the code. For example, let's install probe on a `read()` call on the side of standard C library:

![image:approbes](appprobes.png)

In DTrace userspace tracing is performed through `pid` provider:
```
	pid1449:libc:__read:entry
```
In this example entry point of `__read()` function from standard C library is patched for process with PID=1449. You may use `return` as name for return probes, or hexademical number -- in this case it will represent an instruction offset inside that function. 

If you need to trace binary file of application itself, you may use `a.out` as module name in probe specification. To make specifying PID of tracing process easier, DTrace provides special macro `$target` which is replaced with PID passed from `-p` option or with PID of command which was run with `-c` option:
```
# dtrace -n '
	pid$target:a.out:main:entry { 
		ustack(); 
	}' -c cat
```

Userspace probes are created with `process().function()` syntax in SystemTap, where process contains path of shared library or executable binary which should be traced. This syntax is similiar to `kernel` syntax (as described in [Probes][lang/probes#stap-syntax]): it supports specifying line numbers, source file names, `.statement()` and `.return` probes:
```
# stap -e '
	probe process("/lib64/libc.so.6").function("*readdir*") {
		print_ubacktrace();
	}' -c ls -d /usr/bin/ls
```
Unlike DTrace, in SystemTap any process which invokes `readdir()` call from standard C library will be traced. Note that we used `-d` option so SystemTap will recognize symbols inside `ls` binary. If binary or library is searchable over `PATH` environment variable, you may omit path and use only library name:
```
# export PATH=$PATH:/lib64/
# stap -e '
	probe process("libc.so.6").function("*readdir*") {
		[...] }' ...
```

SystemTap uses _uprobes_ subsystem to trace userspace processes, so `CONFIG_UPROBES` should be turned on. It was introduced in Linux 3.5. Before that, some kernels (mostly RedHat derivatives) were shipped with _utrace_ which wasn't supported by vanilla kernels. It is also worth mentioning that like with kernel tracing, you will need debug information for processes you want to trace that is shipped in `-debuginfo` or `-dbg` packages.

Like with kernel probes, you may access probe arguments using `arg0`-`argN` syntax in DTrace and `$arg_name` syntax in SystemTap. Probe context is also available. Accessing data through pointers however, would requre using `copyin()` functions in DTrace and `user_<type>()` functions in SystemTap as described in [Pointers][lang/pointers] section. 

!!! WARN
Tracing multiple processes in DTrace is hard -- there is no `-f` option like in `truss`. It is also may fail if dynamic library is loaded through `dlopen()`. This limitations, however, may be bypassed by using destructive DTrace actions. Just track requred processes through process creation probes or `dlopen()` probes, use `stop()` to pause process execution and start required DTrace script. `dtrace_helper.d` from JDK uses such approach.
!!!