### Introduction

Both DTrace and SystemTap languages have C-like syntax for dynamic tracing scripts. Every script is a set of probes, and each of them binds to a certain event in kernel or application, for example dispatching of a process, parsing SQL query, etc. Each probe may have a predicate which acts as a filter of unnecessary probes, i.e. if you want to trace specific process or specific kind of query. 

Each script consists of global variables declarations followed by probes, and possibly function declarations. In SystemTap each declaration is preceded by `global`, `function` or `probe` keyword:
```
global counter;
function inc_counter() {
	++counter;
}
probe timer.s(1) {
	inc_counter();
	println(counter);
}
```

!!! NOTE
Trailing semicolons may be omitted in SystemTap Language, but we will use them in our demonstration scripts to improve readability.
!!!

Same works for DTrace, but the syntax of definitions is different:
```
int xcounter;
tick-1s {
    ++xcounter;
    trace(xcounter);
}
```

DTrace language is limited due to safety reasons, so it doesn't support loops and conditional statements. Conditional branch in DTrace may be emulated using predicates, and also a limited support of ternary operator `?:` is available. SystemTap, on the other hand, supports wider subset of C language: it has `for`, `while`, `if`/`else`, `foreach` statements, and `break`/`continue` for controlling loop behavior.

SystemTap supports declaration of functions:
```
function dentry_name:string(dentry:long) {
	len = @cast(dentry, "dentry")->d_name->len;
	return kernel_string_n(@cast(dentry, "dentry")->d_name->name, len);
}
```
In this example, function `dentry_name()` accepts `dentry` argument of type `long` (in this case, `long` is equivalent to a missing pointer type) and returns a string. It converts received pointer to a type `struct dentry`, extracts string from it and returns it.

DTrace doesn't have a functions, but you may use C macro in simple cases:
```
#define CLOCK_TO_MS(clk)      (clk) * (`nsec_per_tick / 1000000)
```

SystemTap language supports `try`/`catch` statement to handle tracing errors which were described in [Safety and errors][tools/safety] section:
```
try {
	/* Errorneous expression: read integer on address 4 */
	println(kernel_int(4));
}
catch(msg) {
	/* Ignore errors or print message `msg` */
}
```

There is a hackish way of building loops in DTrace using timer probes:
```
int count;
BEGIN {
	count = 10;
}
timer-1ms
/--count > 0/ {
	printf("Hello, world!\n");
}
```
This script prints "Hello, world" phrase each millisecond 10 times. 

Finally, SystemTap have Embedded C extension (enabled only in Guru-Mode or in tapsets), which allow to write raw C code compiled directly to module's code without passing first three stages of translation:
```
function task_valid_file_handle:long (task:long, fd:long) %{ /* pure */
	[...]
	
	rcu_read_lock();
	if ((files = kread(&p->files))) {
		filp = fcheck_files(files, STAP_ARG_fd);
		STAP_RETVALUE = !!filp;
	}

	CATCH_DEREF_FAULT();
	rcu_read_unlock();
%}
```

This example is taken from _pfiles.stp_ sample. It has to grab RCU lock to access file pointer safely, which is done by direct call to `rcu_read_lock()` and `rcu_read_unlock()` functions. Note that to access arguments and return value it has to use names prefixed with `STAP` (in early versions of SystemTap there were magic pointers `THIS` and `CONTEXT` for this). To read pointer safely it uses `kread()` function. 

Embedded C part starts with `%{` and ends with `%}` and may be used as function body, and in global scope if you need extra includes.
