### Predicates 

_Predicates_ are usually go in the beginning of the probe and allow to exclude unneccessary data from output, thus saving memory and processor time. Usually predicate is a conditional expression, so you can use C comparison operators in there such as `==`, `!=`, `>`, `>=`, `<`, `<=` and logical operators `&&` for logical AND, `||` for logical OR and `!` for logical negation, alas with calling functions or actions.

In DTrace predicate is a separate language construct which is going in slashes `/` immediately after list of probe names. If it evaluated to true, probe is __executed__:
```
syscall::write:entry 
/pid == $target/
{
    printf("Written %d bytes", args[3]);
}
```

In SystemTap, however, there is no separate predicate language construct, but it supports conditional statement and `next` statement which exits from the probe, so combining them will give similiar effect:
```
probe syscall.write {
   if(pid() != target())
       next;

   printf("Written %d bytes", $count);
}
```
Note that in SystemTap, probe will be __omitted__ if condition in `if` statement is evaluated to true thus making this logic inverse to DTrace.

`$target` in DTrace (macro-substitution) and `target()` context function in SystemTap have special meaning: they return PID of the process which is traced (command was provided as `-c` option argument or its PID was passed as `-p`/`-x` option argument). In these examples only `write` syscalls from traced process will be printed.

!!! WARN
Sometimes, SystemTap may trace its consumer. To ignore such probes, compare process ID with `stp_pid()` which returns PID of consumer.
!!!