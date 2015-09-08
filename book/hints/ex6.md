### Exercise 6

This exercise is not so different than any [latency measurement][principles/perf#latency] script where latency is measured as difference between timestamps of two probe firings and saved to an aggregation. 

Note that `plockstat$` provider doesn't serve a probe for mutex lock attempt, so we had to expand it by using `pid$` provider. As you may notice from ustack outputs in `pthread.d` example, mutex lock attempts are implemented by `mutex_lock_impl()` libc function. We will use `quantize()` aggregation which will be printed with `printa`:

````` scripts/dtrace/mtxtime.d

You will need to bind this script to tsexperiment process using `-c` or `-p` option.

We will need to use static probes `mutex_entry` and `mutex_acquired` for a SystemTap version of that script. However, we will need to be careful while working with userspace backtraces. First of all, we should use `-d` option to provide path to SystemTap for resolving symbols or `--ldd` to make it scan library dependencies of traced binary and automatically add them (when some of them are missing, `stap` utility will provide a hint with full paths).

Mutexes are also often used in TSLoad which can cause excessive overheads when we try to trace them, especially when we will use `ubacktrace()` function. You can use `STP_NO_OVERLOAD` macro definition (which can be passed to `stap` with `-D` option) to prevent stap from failing when overheads are big, or you can reduce overheads. In our case we will limit amount of traced callers by using `ucallers()` function which accepts depth of backtrace as a first argument like `ustack()` function from backtrace and only collects addresses without resolving them to symbols. We will defer symbol resolving to an aggregation printing.

Here are our script for SystemTap:

````` scripts/stap/mtxtime.stp
