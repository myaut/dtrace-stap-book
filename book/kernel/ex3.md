### Exercise 3

#### Part 1

Modify `dumptask.stp` and `dumptask.d` so it will print information on successfull binary load by `execve()` and before process exit. Write a simple program `lab3.c`:

````` scripts/src/lab3.c

Compile it with GCC:
```
# gcc lab3.c -o lab3
```

Run changed scripts and run your program in different ways:

 * Run it with argument:
```
# ./lab3 arg1
```
 * Create a symbolic link and run a program through it:
```
# ln -s lab3 lab3-1
# ./lab3-1
```
 * Created chrooted environment and run `lab3` inside it:
```
# mkdir -p /tmp/chroot/bin /tmp/chroot/lib64 /tmp/chroot/lib
# mount --bind /lib64 /tmp/chroot/lib64   		(in Linux)
# mount -F lofs /lib /tmp/chroot/lib			(in Solaris)
# cp lab3 /tmp/chroot/bin
# chroot /tmp/chroot/ /bin/lab3
```

What data output has been changed? Try to explain these changes.

#### Part 2

Shell scripts have overhead caused by need to spawn new processes for basic operations, and thus calling `fork()` and `execve()`. Write SystemTap and DTrace scripts that measure following characteristics:
 * time, spent for `fork()` and `execve()` system calls;
 * time, spent for child process initialization in userspace: closing files and resetting signals -- it is time interval between finish of `fork()` call in child context and calling of `execve()`;
 * own program time after it was loaded with `execve()` and before it was exited.
 
To be more correct, we should also measure time spent by `ld.so` loader and substract it from _own program time_, but it involves complex tracing of userspace, so it is out of scope of this exercise. 

Measure all time periods in microseconds and save them to an aggregations using process executable name and its program arguments.

Use `proc_starter` default experiment to demonstrate written script. This module starts `sh` shell (which can be overridden with `shell` parameter), uses `PS1` environment variable to reset prompt, and simulates real user entering commands by passing them through pseudo-terminal. Commands are represented as probability map `command`.