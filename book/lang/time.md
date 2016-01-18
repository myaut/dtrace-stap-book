### [__index__:monotonic time] [__index__:wall-clock time] Time

A man used to live with a calendar and 24-hour representation of time. Coordinated Universal Time (UTC) is used for that now. These details are not needed for most kernel or application processes, so there is multiple time sources available for tracing tools:

--- %60,20,20
__Time source__ | __DTrace__ | __SystemTap__
_System timer_ is responsible for handling periodical events in kernel such as context switch. System timer usually ticks at constant frequency (but ticks may be omitted in _tickless kernels_). Interval between firing timer is usually referred as special unit of time: _tick_, _lbolt_ in Solaris or _jiffy_ in Linux. Timer frequency in Linux can be get using `HZ()` function. | `\`lbolt` or `\`lbolt64` | `jiffies()`
_Processor cycles counter_ is a special CPU register which act as a counter which increases on each cycle, such as `TSC` in x86 or `%tick` in SPARC. It may not be monotonic. | | `get_cycles()`
_Monotonic time_. Starts at unspecified moment of time (usually at system boot), but ticks with constant intervals. May use high-resolution time source such as HPET on x86, but may impose some jitter between CPU cores or CPUs. | `timestamp` | `local_clock_<unit>()` or `cpu_clock_<unit>(<cpu>)`
_Virtual monotonic time of thread_. Similar to previous time source, but only accounts when thread is on CPU, which is useful to calculate CPU usage of a thread | `vtimestamp` |
_Real time_ or _Wall-clock time_. Monotonic time source which starting point is an UNIX Epoch (00:00:00 UTC, Thursday, 1 January 1970). May use extra locks, access RTC, so it generally slower than previous time sources | `walltimestamp` | `gettimeofday_<unit>()`
---

In this examples `<unit>` is one of (`s` -- seconds, `ms` -- milliseconds, `us` -- microseconds and `ns` -- nanoseconds). DTrace time sources always have nanosecond resolution.

Generally speaking, monotonic time sources are better for measurement relative time intervals, while real time is used if you need precise timestamp of an event (i.e. for cross-referencing with logs). To print a real timestamp, use `ctime()` function in SystemTap which converts time to string, or use `%Y` format specifier in DTrace print functions. 

#### References

* ![image:dtraceicon](icons/dtrace.png) [Built-in Variables](http://docs.oracle.com/cd/E19253-01/817-6223/chp-variables/index.html#6mlkidlfu)
* ![image:stapset](icons/stapset.png) [Timestamp Functions](https://sourceware.org/systemtap/tapsets/timestamp_stp.html)