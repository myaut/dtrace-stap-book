### Exercise 1

Write `opentrace.d` and `opentrace.stp` scripts which are tracing `open()` system calls. They should print following information in one line:
 * Call context: name of executable file, process ID, user and group IDs of user and group which are executing prcoess.
 * Path to file which should be opened.
 * A string containing `open()` flags `O_RDONLY`, `O_WRONLY`, `O_RDWR`, `O_APPEND`, `O_CREAT`
 * Return value of system call
 
For example:
```
tee[939(0:0)] open("/tmp/test", O_WRONLY|O_APPEND|O_CREAT) = 3
```

Bit flags values are presented in following table:

---
__Flag__ | __Solaris__ | __Linux (x86)__
`O_RDONLY` |2,1 bits 0-1 are not set
`O_WRONLY` | 1 | 1
`O_RDWR` | 2 | 2
`O_APPEND` | 8 | 1024
`O_CREAT` | 256 |64
---

Test script that your created by experimenting with redirection to file or a pipe with `tee` tool:
```
# cat /etc/inittab > /tmp/test
# cat /etc/inittab >> /tmp/test
# cat /etc/inittab | tee /tmp/test
# cat /etc/inittab | tee -a /tmp/test
```

!!! WARN
In Solaris 11 `open()` system call was replaced with more generic `openat()`.
!!!

_Optional_: Modify your scripts so only files that have "/etc" in their path will be shown.