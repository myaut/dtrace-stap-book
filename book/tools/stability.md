### Stability

Another problem to which dynamic tracing systems face is stability of in-kernel interfaces. While system calls never change their interface due to backwards compability (if something need to be changed, new system call is introduced<sup>†</sup>), internal kernel function often do that especially if they not a public API for a drivers. Dynamic tracing languages provide mechanisms to avoid direct use of in-kernel interface by hiding them in abstractions:

---
__Stability__ |2,1 __Data access__ |2,1 __Tracepoints__
           | DTrace | SystemTap | DTrace | SystemTap
High | _translators_, i.e. `fileinfo_t`  | tapset variables |1,2 statically defined tracing providers (`sdt` and many others) | tapset aliases, i.e. `vm.kfree`
Mediocre |1,2 Global variables and raw arguments like `args[0]` or `(struct_t*) arg0` |1,2 Raw arguments like `$task` or `@cast($task, "task_struct")`  | statically defined ftrace probes like `kernel.trace("kfree")`
Lowest  | `fbt` and `pid$$` providers | DWARF probes like `kernel.function("kfree")`
---

So to achieve maximum script portability, you should pick highest stability options wherever possible. Downside of that approach is that it provider lesser information than you could access with other approaches. These options will be described in [Translators and tapsets][lang/tapset] section of next module. 

Linux kernel is changing faster: it has stable releases each 2-3 months, and moreover, its builds are configurable, so some features present in one kernel may be disabled in another and vice versa which makes stability is much more fragile. To overcome that, SystemTap Language has conditional compilation statements which like in C allow to disable certain paths in code. Simplest conditional compilation statements are `@defined` which evaluates to true if variable passed to it is present in debug information and `@choose_defined` which chooses from several variables. It also support ternary conditional expression:
```
	%( kernel_v >= "2.6.30" 
		%? count = kernel_long($cnt)
		%: count = $cnt 
	%)
```

Here, `kernel_v` is numerical version of kernel without suffix (for version with suffix, use `kernel_vr`). SystemTap also defines `arch` variable and `CONFIG_*` tokens similiar to configuration options. These options are not available in Embedded C, use traditional preprocessor there.

Finally, if some probe is missing from kernel, script compilation will fail. DTrace allow to ignore such errors by passing `-Z` command line option. In SystemTap you may add `?` at the end of probe name to make this probe optional.

#### Notes

† -- unless you are running Solaris 11 which was deprecated and obsoleted many of its system calls..

#### References

 * ![image:staplang](icons/staplang.png) [Conditional compilation](https://sourceware.org/systemtap/langref/Language_elements.html#SECTION00068000000000000000)
 * ![image:dtraceicon](icons/dtrace.png) [Stability](http://docs.oracle.com/cd/E19253-01/817-6223/chp-stab/index.html)
 