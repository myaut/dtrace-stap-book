### Associative arrays

!!! DEF
_Associative array_ is a sequence of values which are accessible through one or more keys. Any types may be used for hashing, but they have to be comparable, and in some cases hashable.
!!!

Associative arrays are useful for saving last observable state related to a some object, so it can be reused in subsequent probes. For example, let's save last read or write operation performed on file. You will need to define keys and value types in DTrace:
```
string last_fop[int, int];
syscall::read:entry, syscall::write:entry { 
	last_fop[pid, (int) arg0] = probefunc; 
}
```

In SystemTap, however, they are deduced from the assignment:
```
global last_fop;
syscall.read, syscall.write { 
	last_fop[pid(), $fd] = pn(); 
}
```

To delete entry from an associative array, it should be assigned to `0` in DTrace or deleted using `delete array[key1];` expression in SystemTap. If value is not exist, both DTrace and SystemTap will return `0` as a default value. 

In DTrace you only can access value in associative array knowing its keys, in SystemTap along with that you can walk entire array with `foreach` statement:
```
foreach([pid+, fd] in last_fop limit 100) {
	printf("%d\t%d\t%s\n", pid, fd, last_fop[pid, fd]);
}
```
Variables for keys are listed in square braces. If variable name ends with `+` or `-`, than keys will be sorted in ascend or descend order correspondingly (only one key may be used for sorting). Optional `limit N` part allows to limit amount of entries.

Maximum amount of entries that associative array can keep is limited by `dynvarsize` tunable in DTrace or `MAXMAPENTRIES` in SystemTap. Additionally, you may explicitly specify maximum number of entries in array:
```
global array[SIZE];
```

!!! WARN
Starting with SystemTap 2.1 it allocates `MAXMAPENTRIES` entries for associative array on per-cpu basis (using not only online, but possible CPUs too) at start (to avoid further allocation faults). Also, it allocates memory for strings statically too. So to keep associative array with string key you will need at least `NR_CPUS * MAXMAPENTRIES * MAP_STRING_LENGTH` which gives 128 megabytes of memory on CentOS 7.0 x86_64.
!!!

#### References

* ![image:dtraceicon](icons/dtrace.png) [Variables/Associative arrays](http://docs.oracle.com/cd/E19253-01/817-6223/chp-variables/index.html#6mlkidlfr)
* ![image:staplang](icons/staplang.png) [Associative arrays](https://sourceware.org/systemtap/langref/Associative_arrays.html)

[aggr]
### Aggregations

_Aggregations_ are most useful for evaluating system performance (they are called _statistics_ in SystemTap). Aggregation will update intermediate set of parameters when new value is added, and when needed provide capability to print statistical characteristics of values sample added to it. Let's for example see how it works for mean value -- dynanamic tracing system saves count of added values and their sum, and when values need to be printed, sum is divided to a count:

![image:aggrs](aggrs.png)

Aggregations in DTrace reside in separate namespace: each name of aggregation begins with at-symbol `@`. Single at-symbol `@` is an alias to `@_` and is a shorter possible aggregation name which is useful for one-liners. Moreover, if it was not printed in the END probe, or timer probe, DTrace will automatically print it for you. There is no need to declare aggregation, and it support key access same way associative array does. When value is added to a aggregation, it is "assigned" to a return value of aggregating function, i.e. `@fds = avg(arg0);` will create an aggregation which calculates mean value of `arg0`.

SystemTap have a statistics. They are do not support indexing like associative arrays (but they may be a values in associative arrays), thus they are special kind a variable. To create a statistic you need to use _aggregate operator_ `<<<` instead of assignment operator `=`, for example: `fds <<< $fd`. Aggregating function is used when result is printed, and begins with `@`, i.e. `@avg(fds)` will return mean value of statistic `fds`. This allows to use single statistic for multiple functions wherever possible.

Here are list of aggregating functions (note that in SystemTap they have to be preceded with `@`):
 * `count` -- counts number of values added
 * `sum` -- sums added value
 * `min`/`max`/`avg` -- minumum, maximum and mean value, respectively
 * `stddev` -- standard deviation (only in DTrace)
 * `lquantize` -- prints linear histogram (`hist_linear` in SystemTap)
 * `quantize` -- prints logarithmic histogram (`hist_log` in SystemTap)
 
The following actions may be performed on aggregations:

---
__Action__ | __DTrace__ | __SystemTap__
Add a value | `@aggr[keys] = func(value);` | `aggr[keys] <<< value;`
Print | `printa(@aggr)` or \
        `printa("format string", @aggr1, @aggr2, ...)` | `println(@func(aggr))` \
                                                         (use `foreach` in case of associative arrays).
Flush values and keys | `clear(@aggr)` (only values) or \
                        `trunc(@aggr)` (both keys and values) | `delete aggr` or `delete aggr[keys]`
Normalize | `normalize(@aggr, value);` and \
            `denormalize(@aggr);` | Use division `/` and multiplication `*` on results of aggregating functions
Limit number of values | `trunc(@aggr, num)` | Use `limit` clause in `foreach`
---

!!! WARN
Aggregations may be sorted in DTrace using `aggsortkey`, `aggsortpos`, `aggsortkeypos` and `aggsortrev` tunables.
!!!

[aggr-example]
Aggregations are extremely useful for writing stat-like utitilies. For example, let's write utilities that count number of `write` system calls and amount of kilobytes they written. 

````` scripts/dtrace/wstat.d

Note that aggregations are follow after keys in `printa` format string, and they are going in the same order they are passed as `printa` parameters. Format fields for aggregations use `@` character. Sorting will be performed according to a PID (due to `aggsortkey` tunable), not by number of operations or amount of bytes written. Option `aggsortkeypos` is redundant here, because `0` is default value if `aggsortkey` is set. 

SystemTap has similiar code, but `printa` is simplemented via our own `foreach` cycle. On the other hand, we will keep only one associative array here:

````` scripts/stap/wstat.stp

Output will be similiar for DTrace and SystemTap and will look like:
```
  PID     EXECNAME  FD     OPS  KBYTES
15881         sshd   3       1       0
16170       stapio   1       1       0
16176       python   8    8052   32208
16176       python   7    8045   32180
16176       python  10    8007   32028
16176       python   9    8055   32220
```

#### References

* ![image:dtraceicon](icons/dtrace.png) [Aggregations](http://docs.oracle.com/cd/E19253-01/817-6223/chp-aggs/index.html)
* ![image:staplang](icons/staplang.png) [Statistics (aggregates)](https://sourceware.org/systemtap/langref/Statistics_aggregates.html)