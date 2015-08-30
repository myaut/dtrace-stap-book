### SystemTap

SystemTap is not part of Linux Kernel, so it have to adapt to kernel changes: i.e. sometimes runtime and code-generator have to adapt to new kernel releases. Also, Linux kernels in most distributions are stripped which means that debug information in DWARF format or symbol tables are removed. SystemTap supports _DWARF-less_ tracing, but it has very limited capabilities, so we need to provide DWARF information to it.

Many distributions have separate packages with debug information: packages with `-debuginfo` suffix on RPM-based distributions, packages with `-dbg` on Debian-based distributions. They have files that originate from same build the binary came from (it is crucial for SystemTap because it verifies buildid of kernel), but instead of text and data sections they contain debug sections. For example, RHEL need `kernel-devel`, `kernel-debuginfo` and `kernel-debuginfo-common` packages to make SystemTap working. Recent SystemTap versions have `stap-prep` tool that automatically install kernel debuginfo from appropriate repositories with correct versions.

For vanilla kernels you will need to configure `CONFIG_DEBUG_INFO` option so debug information will be linked with kernel. You will also need to set `CONFIG_KPROBES` to allow SystemTap patching kernel code, `CONFIG_RELAY` and `CONFIG_DEBUG_FS` to allow transfer information between buffers and consumer and `CONFIG_MODULES` with `CONFIG_MODULE_UNLOAD` to provide module facilities. You will also need uncompressed `vmlinux` file and kernel sources located in `/lib/modules/$(uname -r)/build/`.

SystemTap doesn't have VM in-kernel (unlike DTrace and KTap), instead it generates kernel module source written in C than builds it, so you will also need a compiler toolchain (`make`, `gcc` and `ld`). Compilation takes five phases: _parse_, _elaborate_ in which tapsets and debuginfo is linked with script, _translate_ in which C code is generated, _compile_ and _run_:

![image:stapprocess](stapprocess.png)

SystemTap uses two sets of libraries during compilation process to provide kernel-version independent API for accessing. _Tapsets_ are a helpers that are written in SystemTap language (but some parts may be written in C) and they are plugged during _elaborate_ stage. _Runtime_ is written in C and used during _compile_ stage. Because of high complexity of preparing source code and compiling that, SystemTap is slower than a DTrace. To mitigate that issue, it can cache compiled modules, or even use compile servers. 

Unlike DTrace, SystemTap has several front-end tools with different capabilities:
 * `stapio` is a consumer which runs module and prints information from its buffer to a file or stdout. It is never used directly, but called by `stap` and `staprun` tools.
 * `stap(1)` includes all five stages and allow to stop at any of them. I.e. combining options `-k` and `-p 4` allow you to create pre-compiled `.ko` kernel module. Note that SystemTap is very strict about version of kernel it was compiled for.
 * `staprun(1)` allows you to reuse precompiled module, instead of start compilation from scratch.
 
!!! WARN
If `stap` parent is exited, than `killall -9 stap` won't finish `stapio` daemon. You have to signal it with SIGTERM: `killall -15 stap`
!!!

[stap]

#### stap 

Like many other scripting tools, SystemTap accepts script as command line option or external file, for example:
 * Command-line script is passed with `-e` option
   `# stap -e 'probe syscall.write { printf("%d\n", $fd); }' [arguments]`
 * External file as first argument:
   `# stap syscalls. [arguments]`
SystemTap command line arguments may be passed to a script, but it distingushes their types: numerical arguments are accessible with `$` prefix: `$1`, `$2` ... `$n` while string arguments have `@` prefix: `@1`, `@2` ... `@n`

Here are some useful `stap(1)` options:
 * `-l PROBESPEC` accepts probe specifier without `probe` keyword (but with wildcards) and prints all matching probe names (more on wildcards in [Probes][lang/probes]). `-L` will also print probe arguments and their types. For example:
   `# stap -l 'scsi.*'`
 * `-v` -- increases verbosity of SystemTap. The more letters you passed, the more diagnostic information will be printed. If only one `-v` was passed, `stap` will report only finishing of each stage.
 * `-p STAGE` -- ends stao process after _STAGE_, represented with a number starting with 1 (_parse_). 
 * `-k` -- won't delete SystemTap temporary files created during compilation (sources and kernel modules kept in `/tmp/stapXXXX` directory),
 * `-g` -- enables Guru-mode, that allows to bind to blacklisted probes and write into kernel memory along with using Embedded C in your scripts. Generally speaking, it allows dangerous actions.
 * `-c COMMAND` and `-x PID` -- like those in DTrace allow to bind tracing to a specific process
 * `-o FILE` -- redirects output to a file. If it already exists, SystemTap __rewrites__ it.
 * `-m NAME` -- when compiling a module, give it meaningful name instead of `stap_<gibberish>`.
 
When SystemTap needs to resolve address into a symbol (for example, instruction pointer to a corresponding function name), it doesn't look into libraries or kernel modules. Here are some useful command-line options that enable that:
 * `-d MODULEPATH` -- enables symbol resolving for a specific library or kernel module. Note that in case it is not provided, `stap` will print a warning with corresponding `-d` option. 
 * `--ldd` -- for tracing process -- use `ldd` to add all linked libraries for a resolving.
 * `--all-modules` -- enable resolving for all kernel modules
 
#### SystemTap example

Here is sample SystemTap script:

```
#!/usr/sbin/stap 

probe syscall.write
{
    if(pid() == target())
      printf("Written %d bytes", $count);
}
```

Save it to `test.stp` and run like this:

```
root@host# stap /root/test.stp -c "dd if=/dev/zero of=/dev/null count=1"
```

__Q__: Run SystemTap with following options: `# stap -vv -k -p4 /root/test.stp `, find generated directory in `/tmp` and look into created C source.

__Q__: Calculate number of probes in a `syscall` provider and number of variables provided by `syscall.write` probe:

```
# stap -l 'syscall.*' | wc -l
# stap -L 'syscall.write'
```

#### References

 * ![image:manpage](icons/manpage.png) [STAP](https://sourceware.org/systemtap/man/stap.1.html)
 * ![image:manpage](icons/manpage.png) [STAPRUN](https://sourceware.org/systemtap/man/staprun.8.html)
 * ![image:staplang](icons/staplang.png) [The stap command](https://sourceware.org/systemtap/langref/SystemTap_overview.html#SECTION00025000000000000000)
 * ![image:staplang](icons/staplang.png) [Literals passed in from the stap command line](https://sourceware.org/systemtap/langref/Language_elements.html#SECTION00067000000000000000)