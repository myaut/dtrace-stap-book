### Exercise 1

This exercise is intended to learn some features of dynamic tracing languages that was discussed in modules 1 and 2. First of all we need to pick probes that we will use in our tracing script. They would be parts of `syscall` provider/tapset. As you can remember from [stap command options][tools/systemtap#stap], probe parameters can be checked with `-L` option:
```
# stap -L 'syscall.open'
syscall.open name:string filename:string flags:long mode:long argstr:string $filename:long int $flags:long int $mode:long int
# stap -L 'syscall.open.return'
syscall.open.return name:string retstr:string $return:long int $filename:long int $flags:long int $mode:long int    
```
Same can be done for dtrace with `-l` option:
```
# dtrace -l -f openat\* -v
   ID   PROVIDER            MODULE             FUNCTION NAME
14167    syscall                               openat entry
 ...
```

Return value (which would represent file descriptor number) will be saved into `$return` variable in SystemTap and `arg1` argument in DTrace. We will also need flags values: `arg2` in DTrace (because they are going third in `openat()` prototype). In SystemTap you can use either DWARF variable `$flags` or tapset variable `flags`. Latter is more stable. 

Similarly, path to opened file will be passed as second `openat()` argument and will be available in DTrace as `arg1` or `$filename`/`filename` in SystemTap. At the moment of system call, however, file path will be a string which is located in user address space, so to get it in tracing script, you will need to copy it by using `copyinstr()` in DTrace or one of `user_string*()` functions. Tapset variable already uses `user_string_quoted()` to access variable, so we will use it in our scripts.

Note that data that we want gather is available in two different probes: flags and file path are provided by entry probe, while file descriptor number can only be collected in return probe (SystemTap can provide flags and file path in return probe, but as we mentioned, it depends on compiler optimizations). Since both probes will be executed in the same context, we can use [thread-local variables][lang/vars#thread-local-vars].

Finally, stringifying flags will require usage of ternary operator `?:` in DTrace or `if/else` construct in SystemTap. To concatenate strings, use `strjoin` from DTrace or string concatenation operator `.` in SystemTap. 

Here are resulting DTrace script which implements required functionality:

````` scripts/dtrace/opentrace.d

I have used `sprintf()` to concatenate strings in SystemTap version of a script:

````` scripts/stap/opentrace.stp

Finally, you will need to add predicates to compare paths with `/etc` in DTrace by using `strstr()` subroutine and comparing it with `0` and SystemTap's `ininstr()` function.
