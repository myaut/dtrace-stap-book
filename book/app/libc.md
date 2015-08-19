### Unix C library

_libc_ is a C library shipped with Unix and provides access to most of its facilities like system calls in portable manner. Linux _glibc_ (one of the implementations of _libc_ which is most popular) and _libc_ shipped with Solaris contain some USDT probes. We will discuss them in this section. 

On Solaris USDT probes are limited to userspace mutexes and read-write locks which available as `plockstat` provider (similiar to [lockstat][kernel/async#lockstat] provider we discussed earlier). _glibc_, however implements wider set of probes: along with various _pthread_ operations which include not only mutexes and rwlocks but also condition variables and threads operations, it supports tracing of `setjmp`/`longjmp` and dynamic linker `ld.so`.

Lets see how mutexes are traced in Solaris and Linux (in this section we will assume glibc by saying "Linux"). Solaris provides them through `plockstat` provider:
```
plockstat<i>pid</i>:::<i>probe-name</i> 
```
SystemTap will use standard USDT notation for it:
```
probe process("libpthread.so.0").mark("<i>probe-name</i>")
```
Note that `libpthread.so.0` will vary in different distributions. We will use defines in our scripts. 

Userspace programs have to explicitly ask kernel to block thread that is waiting on condition variable or mutex. Linux provides `futex` system call for it which is wrapped into so-called _low-level-locks_ in glibc (they are seen by probes those name start with `lll`). Solaris provides multiple `lwp_*` system calls for it like `lwp_park` which "parks" thread (stops its execution).

Here are list of probes available for userspace mutexes (use them as probe name). First argument (`arg0` in DTrace or `$arg1` in SystemTap) would be address of pthread mutex. Some probes can contain more arguments, i.e. DTrace will pass number of spinning loops to `mutex-spun` probe. Check documentation for them.

---
 __Action__ | __DTrace__ | __SystemTap__
Creation                | -                   | `mutex_init`
Destruction             | -                   | `mutex_destroy`
Attempt to acquire      | -                   | `mutex_entry`
Busy waiting (spinning) | `mutex-spin`  >>>   \
                          `mutex-spun`        | -
Attempt to block        | `mutex-block`       | `lll_lock_wait`
Acquired mutex          |  `mutex-blocked` >>>  \
                           `mutex-acquire` >>>  \
                           `mutex-error`         | `mutex_release` >>>  \
                                                   `lll_futex_wake`
---

Here are an example of pthread tracer in SystemTap:

````` scripts/stap/pthread.stp

If we set tsexeperiment process as a target, we can see how request is passed from control thread to a worker thread (some output is omitted):
```
[8972] process("/lib64/libpthread.so.0").mark("mutex_entry") 0xe1a218
  0x7fbcf890fa27 : tpd_wqueue_put+0x26/0x6a [/opt/tsload/lib/libtsload.so]
[8972] process("/lib64/libpthread.so.0").mark("mutex_acquired") 0xe1a218
 0x7fbcf890fa27 : tpd_wqueue_put+0x26/0x6a [/opt/tsload/lib/libtsload.so]
[8972] process("/lib64/libpthread.so.0").mark("cond_broadcast") 0xe1a240
[8972] process("/lib64/libpthread.so.0").mark("mutex_release") 0xe1a218
 0x7fbcf890fa27 : tpd_wqueue_put+0x26/0x6a [/opt/tsload/lib/libtsload.so]
[8971] process("/lib64/libpthread.so.0").mark("mutex_entry") 0xe1a628
 0x7fbcf9148fed : cv_wait+0x2d/0x2f [/opt/tsload/lib/libtscommon.so]
 0x7fbcf890f93f : tpd_wqueue_pick+0x44/0xbc [/opt/tsload/lib/libtsload.so]
[8971] process("/lib64/libpthread.so.0").mark("mutex_acquired") 0xe1a628
```

Note that thread with TID=8972 will acquire mutex in `tpd_wqueue_put` function and then send a broadcast message to all workers. One of them (one with TID=8971) wakes up, re-acquires mutex and gets request through `tpd_wqueue_pick`. 

`plockstat` doesn't support many probes that glibc do, put we can easily replace them with `pid` provider and function boundary tracing:

````` scripts/dtrace/pthread.d

That script yields similiar results on Solaris:
```
[7] mutex_lock_impl:mutex-acquire   0x46d4a0                        [46d4a0]
              libtsload.so`tpd_wqueue_put+0x26
[7] cond_signal:entry   0x46d4e0                                    [46d4e0]
[7] mutex_unlock_queue:mutex-release   0x46d4a0                     [46d4a0]
[7] mutex_unlock_queue:mutex-release   0x46d4a0                     [46d4a0]
[6] mutex_lock_impl:mutex-acquire   0x46d4a0                        [46d4a0]
              libtsload.so`tpd_wqueue_pick+0xb6
[6] pthread_cond_wait:return   0x15                                 [15]
```


#### References

* [glibc documentation on SystemTap probes](https://sourceware.org/git/?p=glibc.git;a=blob;f=nptl/DESIGN-systemtap-probes.txt)
* ![image:dtraceicon](icons/dtrace.png) [plockstat Provider](http://docs.oracle.com/cd/E19253-01/817-6223/chp-plockstat/index.html)