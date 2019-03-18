### [__index__:predicate] Predicates 

_Predicates_ are usually go in the beginning of the probe and allow to exclude unnecessary data from output, thus saving memory and processor time. Usually predicate is a conditional expression, so you can use C comparison operators in there such as `==`, `!=`, `>`, `>=`, `<`, `<=` and logical operators `&&` for logical AND, `||` for logical OR and `!` for logical negation, alas with calling functions or actions.

In DTrace and BPFTrace predicate is a separate language construct which is going in slashes `/` immediately after list of probe names. If it evaluated to true, probe actions are __executed__:
```
syscall::write:entry 
/pid == $target/
{
	printf("Written %d bytes", args[3]);
}
```

In SystemTap, however, there is no separate predicate language construct, but it supports conditional statement and `next` statement which exits from the probe, so combining them will give similar effect:
```
probe syscall.write {
	if(pid() != target())
		next;
	printf("Written %d bytes", $count);
}
```
Note that in SystemTap, probe will be __omitted__ if condition in `if` statement is evaluated to true thus making this logic inverse to DTrace.

Starting with SystemTap 2.6, it supports mechanism similar to predicates which is called on-the-fly arming/disarming. When it is active, probes will be installed only when certain condition will become true. For example:
```
probe syscall.write if(i > 4) {
		printf("Written %d bytes", $count);
}
```
This probe will be installed when `i` becomes more than four. 

[__index__:processes, grabbing PID] `$target` in DTrace (macro-substitution) and `target()` context function in SystemTap have special meaning: they return PID of the process which is traced (command was provided as `-c` option argument or its PID was passed as `-p`/`-x` option argument). In these examples only `write` syscalls from traced process will be printed. 

There is no equivalent of this in BPFTrace, however similar behaviour can be achieved with macro arguments: 
```
# bpftrace -e '
    tracepoint:syscalls:sys_enter_write
    / pid == $1 / {
        /* actions */
    }' $(pgrep -f myprogram)
```
In this example, `pgrep -f myprogram` will return a pid of some program, and it will be used as `$1` macro substitution in BPFTrace code.

!!! WARN
Sometimes, SystemTap may trace its consumer. To ignore such probes, compare process ID with `stp_pid()` which returns PID of consumer.
!!!

Sometimes, if target process forking and you need to trace its children, like with `-f` option in `truss`/`strace`, comparing `pid()` and even `ppid()` is not enough. In this case you may use DTrace subroutine `progenyof()` which returns non-zero (treated as true) value if current process is a direct or indirect child of the process which ID was passed as parameter. For example, `progenyof(1)` will be true for all userspace processes because they are all children to the `init`.

`progenyof()` is missing both in BPFTrace and SystemTap, but it can be simulated with `task_*()` functions and the following SystemTap script (these functions are explained in [Process Management][kernel/proc#task-funcs]):
```
function progenyof(pid:long) {
	parent = task_parent(task_current());
	task = pid2task(pid);

	while(parent && task_pid(parent) > 0) {
		if(task == parent)
			return 1;

		parent = task_parent(parent);
	}
}

probe syscall.open { 
	if(progenyof(target())) 
			printdln(" ", pid(), execname(), filename);
}
```

Assume that 2953 is a process ID of bash interactive session, where we open child `bash` and call `cat` there:
```
root@lktest:~# bash
root@lktest:~# ps
	PID TTY          TIME CMD
	2953 pts/1    00:00:01 bash
	4794 pts/1    00:00:00 bash
	4800 pts/1    00:00:00 ps
root@lktest:~# cat /etc/passwd
[...]
```

`cat` is shown by this script even if it is not direct ancestor of `bash` process that we are tracing:
```
# stap ./progeny.stp -x 2953 | grep passwd
4801 cat /etc/passwd
```

