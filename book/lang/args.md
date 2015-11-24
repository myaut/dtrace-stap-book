### Arguments

When you bind a probe, you need to collect some data in it. In C, data is usually passed as arguments to a function, or returned as _return value_. So, when you bind a function boundary tracing probe, you may need to gather them. Argument extraction relies on calling conventions, and extracts data directly from registers or stack.

For example, let's look at Solaris kernel function from ZFS: `void spa_sync(spa_t *spa, uint64_t txg);`. First argument is ZFS representation of a pool, second is 64-bit unsigned integer which is transaction group number. So when we bind a probe to a `spa_sync`, we can print both of them:
```
# dtrace -qn '
	::spa_sync:entry { 
		printf("synced txg=%d [%s]\n", 
			args[1], args[0]->spa_name); }' 
```

DTrace supports two forms of arguments: `arg0`, `arg1` ... `argN` are `uint64_t` values, while `args[0]`, `args[1]` ... `args[N]` have actual types if DTrace is able to extract them (i.e. DTrace forbids type hinting for unstable probes). If `args[N]` is unavailable, you can still treat `argN` as pointer and covert it as you want:
```
# dtrace -qn '
	::spa_sync:entry { 
		printf("synced txg=%ld [%s]\n", 
			(long) arg1, ((spa_t*) arg0)->spa_name); }' 
```

DTrace supplies two arguments for return probes: `arg0` is an instruction pointer to a caller, and `arg1` or `args[1]` is a return value.

DWARF format used in Linux is richer than CTF from Solaris and saves not only argument types, but their names too. They are provided in SystemTap in separate namespace beginning with `$` and followed by name of argument. It provides access to locals as well as arguments. However, some of them may be unavailable at the probe, because they are overwritten by other data (which is called _optimized out_). For example, let's look at `vfs_read` function from Linux kernel:
```
ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos) {
	ssize_t ret;

	[...]

	return ret;
}
```

Unfortunately, variable `ret` is inaccessible at the return probe, but you can still get it from `%rax` register on x86_64 which is used for saving return values. SystemTap supplies return values in `$return` variable:
```
# stap -e '
	probe kernel.function("vfs_read").return { 
		printf("VARS:%s\nreturn: %d\n", $$vars, $return);
		exit(); }'
VARS: file=0xcfa79580 buf=0xbf9fa8b8 count=0x2004 pos=0xcf2e9f98 ret=?
return: 12
```

To handle such situations (and many others, i.e. when name of argument was changed in current kernel), you may use `@defined` expression, or `@choose_defined` which works like ternary operator: `@choose_defined($a, $b)` is equivalent to `@defined($a)? $a : $b`. Here is an example of `@defined`:
```
if (@defined($var->field)) { 
	println($var->field);
} 
```

If you want to print all arguments simultaneously, you should carefully handle each argument. However, SystemTap can do it automatically. Such strings provided in meta-variables:
 * `$$parms` contains function arguments with their names
 * `$$locals` contains local variables with their names
 * `$$vars` contains both `$$parms` and `$$locals`
 * `$$return` contains return value.
An example of `$$vars` may be found above.

Finally, SystemTap allows to convert arguments to strings, including pretty representation of structure pointers when all fields are read, if trailing dollar sign is added to an argument:
```
# stap -e '
	probe kernel.function("vfs_read") { 
		println($file$); }'
```

#### References

 * ![image:staplang](icons/staplang.png) [Built-in probe point types (DWARF probes) ](https://sourceware.org/systemtap/langref/Probe_points.html#SECTION00052000000000000000)
 * [Troublesome Context Variables](https://sourceware.org/systemtap/wiki/TipContextVariables)
