### Exercise 7

Create two scripts: `topphp.d` and `topphp.stp` which will measure mean execution time of each PHP function and count number of calls to that function. Group functions by request URI and full function name including class name (if defined). Use `drupal` experiment to demonstrate your script.

!!! NOTE
It would be reasonable to run workload generator on other system (so it won't affect execution of server). You can switch roles of virtual machines in lab environment i.e. use Solaris as server and Linux as client and vice versa. To alter server's address, use `-s` option in `tsexperiment` command line:
```
# /opt/tsload/bin/tsexperiment -e drupal/ run  \
    -s workloads:drupal:params:server=192.168.13.102
```
!!!
