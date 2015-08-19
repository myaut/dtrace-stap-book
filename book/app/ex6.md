### Exercise 6

Implement two scripts: `mtxtime.d` and `mtxtimd.stp` that would compute delay between attempt to acquire a userspace mutex and a moment when mutex is acquired. Group times by user stacks and print data as logarithmic histograms.

Use `pthread` experiment to demostrate your scripts, like in previous section, TSLoad workload generator itself would be an object in the experiment. Try to identify mutexes that show delays larger than 1 ms. 

!!! WARN
To prevent problems with symbol resolving in DTrace after tracing process finishes, you can attach to a function `experiment_unconfigure()` from `tsexperiment` to print gathered data. 
!!!