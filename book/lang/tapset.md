### Tapsets & translators

We already discussed problem with probe stability. Some issues may be related to changing data structures in kernel, or several variants may exist in kernel, for example for 32- and 64-bit calls. Let's see how access to fields of that structure may be unified.

[__index__:translators (DTrace)] DTrace has a _translators_ for doing that:

````` scripts/dtrace/stat.d

In this example translator describes rules of converting source structure `stat64_32` to a structure with known format defined in DTrace `stat_info`. After that, `xlate` operator is called which receives pointer to `stat64_32` structure to a `stat_info`. Note that our translator also responsible for copying data from userspace to kernel. Built-in DTrace translators are located in `/usr/lib/dtrace`.

[__index__:tapset] [__index__:prologue probe alias] [__index__:epilogue probe alias] SystemTap doesn't have translators, but you can create _prologue_ or _epilogue alias_ which performs necessary conversions before (or after, respectively) probe is called. These aliases are grouped into script libraries called _tapsets_ and put into `/usr/share/systemtap/tapset` directory. Many probes that we will use in following modules are implemented in such tapsets. 

Linux has several variants for `stat` structure in `stat()` system call, some of them deprecated, some are intended to support 64-bit sizes for 32-bit callers. By using following tapset we will remove such differences and make them universally available through `filename` and `size` variables:

````` scripts/stap/tapset/lstat.stp

This example is unrealistic: it is easier to attach to `vfs_lstat` function which has universal representation of `stat` structure and doesn't involve copying from userspace. Summarizing the syntax of creating aliases:
```
probe <i>alias-name</i> {=|+=} <i>probe-name-1</i> [?] [,<i>probe-name-2</i> [?] ...] <i>probe-body</i>
```
Here `=` is used for creating prologue aliases and `+=` is for epilogue aliases. Question mark `?` suffix is optional and used if some functions are not present in kernel -- it allows to choose probe from multiple possibilities.

!!! WARN
Note that this tapset only checks for 64-bit Intel architecture. You will need additional checks for PowerPC, AArch64 and S/390 architectures.
!!!

After we created this tapset, it can be used very easy:

````` scripts/stap/lstat.stp

Also, sometimes we have to define constants in dynamic tracing scripts that match corresponding kernel or application constants. You can use enumerations for that in DTrace, or define a constant variable with `inline` keyword:
```
inline int TS_RUN = 2;
```
You may use initializer for global variable to do that in SystemTap:
```
global TASK_RUNNING = 0;
```
If you have enabled preprocessor with `-C` option, you may use `#define` to create macro as well.

#### References

* ![image:dtraceicon](icons/dtrace.png) [Translators](http://docs.oracle.com/cd/E19253-01/817-6223/chp-xlate/index.html)
* ![image:staplang](icons/staplang.png) [Probe aliases](https://sourceware.org/systemtap/langref/Components_SystemTap_script.html#SECTION00042000000000000000)