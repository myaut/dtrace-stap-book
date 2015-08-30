### Exercise 2

We will have to use `count()` [aggregation][lang/assocarr#aggr] to count `open()` and `openat()` system calls. It can be cleaned up from outdated data wuth `trunc()` action in DTrace or `delete` operation in SystemTap. These scripts are roughly based on `wstat.d` and `wstat.stp` from [aggregations example][lang/assocarr#aggr-example].

To print current timestamp we can use `%Y` formatting specifier and `walltimestamp` variable in DTrace. Same can be achieved with `ctime()` and `gettimeofday_s()` functions from SystemTap. To print data periodically, we can use [timer probes][lang/probes#timers]: `timer.s($1)` in SystemTap or `tick-$1s` from DTrace. `$1` here represents first command line argument.

Finally, we need to determine if open operation requests creation of file or not. We should write predicate for that which tests flags passed to open for `O_CREAT` flag (we have learned how to access flags in previous exercize). 

Here are resulting scripts:

````` scripts/dtrace/openaggr.d
````` scripts/stap/openaggr.stp

