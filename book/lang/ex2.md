### Exercise 2

Modify scripts from Exercise 1 so they count following statistics for processes that are running in a system:
 * number of attempts to open existing file;
 * number of attempts to create a file;
 * number of successful attempts.
 
At a period that is defined as command line arguments (specified in seconds) script should print:
 * Current time and day in human-readable format.
 * Table that contains gathered statistics per process along with that process name and PID.
Numbers should be cleared during each iteration. 

You can use module `file_opener` to demonstrate your scripts. This module uses working directory which is passed as `root_dir` parameter, fills it with some files that are created preliminary (their number is set by `created_files` parameter). While executing request, it uses `file` random variable (which range is cut to `[1;max_files)`) and either tries to create a file or open it depending on `create` parameter. 

Run several experiments using TSLoad workload generator varying `created_files` parameter and compare the results:
```
# EXPDIR=/opt/tsload/var/tsload/file_opener
# for I in 1 2 3; do
	mkdir /tmp/fopen$I
	tsexperiment -e $EXPDIR run                             \
			-s workloads:open:params:root_dir=/tmp/fopen$I  \
			-s workloads:open:params:created_files=$((I * 160)) &
done
```

Try to explain differences you get from the nature of `file_opener` workload generator module. 