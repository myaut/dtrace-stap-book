### Non-native languages

As DTrace became popular, many language interpreters got USDT probes. Some of them adopted them in upstream, some probes are provided by the binaries custom packages shipped with operating system. The basic pair of probes provided by most language interpreters are function entry and exit probes which provide name of the function, line number and file name. For example, Perl can be traced that way:

```
# echo 'use Data::Dumper; 
      map { Dumper($_, ", ") }  ("Hello", "world");' | 
    dtrace -n '
        perl$target:::sub-entry {
            trace(copyinstr(arg0));  trace(copyinstr(arg1)); trace(arg2);
        }  ' -c 'perl -- -'
```

```
# stap -e '
        probe process("/usr/lib64/perl5/CORE/libperl.so").mark("sub__entry") {
            printdln(" : ", user_string($arg1), user_string($arg2), $arg3);
        }
    ' -c $'perl -e \'use Data::Dumper; 
                     map { Dumper($_, ", ") }  ("Hello", "world");\''
```

Note that we had to use stdin as a script in DTrace example. That happened because DTrace cannot parse `-c` option value in shell-like manner.

Language interpreters provide not only function entry probes, here are other examples of supplied probes:

    * Function entry and exit probes.
        * In PHP and Python -- `function-entry`/`function-return`.
        * In Perl -- `sub-entry`/`sub-return`.
        * In Ruby -- `method-entry`/`method-return`.
        * In Tcl -- `proc-entry`/`proc-return`.
    * Probes that fire inside function: `line` in Python which corresponds to a interpreted line and `execute-entry`/`execute-return`, which fire per each Zend interpreter VM operation.
    * Probes of file execution and compilation: such as `compile-file-entry`/`compile-file-return` in PHP and `loading-file`/`loaded-file` in Perl
    * Error and exception probes: `raise` in Ruby and `exception-thrown`/`exception-caught`/`error` in PHP
    * Object creation probes: `obj-create`/`obj-free` in Tcl, `instance-new-*`/`instance-delete-*` in Python, `object-create-start`/`object-create-done`/`object-free` in Ruby
    * Garbage collector probes: `gc-start`/`gc-done` in Python, `gc-*-begin`/`gc-*-end` in Ruby 2.0 or `gc-begin`/`gc-end` in Ruby 1.8

Here are list of availability of that probes in various interpreters shipped as binary packages. If you lack them, you may want to rebuild interpreters with some configure option like `--enable-dtrace`.

---
_Interpreter_ | _CentOS_ | _Solaris_
_Python 2_ |2,1 Python has never accepted DTrace patches into upstream. \
                  However, it was implemented by Solaris developers for Python 2.4, \
                  and being ported to Fedora's and CentOS python. Only function-related \
                  probes are supplied: `function-entry` and `function-return`.
1,2 _Python 3_ | Like Python 2, Python 3 in CentOS (if installed from EPEL) supports `function__entry` \
             and `function__return` probes. In addition to that, SystemTap supplies example python3 tapset. | \
             Python 3 is supplied as FOSS (unsupported) package in Solaris 11 and has `line` probe, \
             instance creation and garbage-collector related probes.
2,1              Starting with Python 3.6, DTrace probes function entry and exit probes, garbage \
                 collector probes and `line` are supported by vanilla interpreter
_PHP5_ | Doesn't support USDT tracing but can it be enabled via `--enable-dtrace` switch when it is built from source. | \
    PHP supports tracing functions, exceptions and errors, VM opcodes execution and file compiling from \
    scratch. Its probes will be discussed in the following section, [Web applications][app/web].
_Ruby 2_ |2,1 Supports multiple probes including object creation, method entry and exit points and garbage   \
           collector probes in Ruby 2.0 in CentOS or Ruby 2.1 as FOSS package in Solaris 11.
_Perl 5_ |2,1 Supports subroutine probes `sub-entry` and `sub-return` (see examples above).
_Go_ | Go is pretty close to native languages in Linux, so you can attach probes directly to its functions while \
       backtraces show correct function names. Differences in type system between C-based languages and Go, however \
       prevents SystemTap from accessing arguments. | \
       Go has experimental support for Solaris so it is not considered as a target for DTrace.
_Erlang_ |2,1 Neither EPEL nor Solaris package feature USDT probes in BEAM virtual machine, but they are supported in \
              sources, so building with `--with-dynamic-trace` option enables various probes including function-boundary probes.
_Node.JS_ |2,1 Node.JS is not supplied as OS packages, while binaries from official site doesn't have USDT enabled in Linux \
               or simply not working in Oracle Solaris (only in Illumos derivatives). Building from sources, however \
               adds global network-related probes like `http-server-request`. Function boundary tracing is not supported.
---

Most interpreted language virtual machines still rely on libc to access basic OS facilities like memory allocation, but some may use their own: i.e. PyMalloc in Python, Go runtime is OS-independent in Go language. For example let's see how malloc calls may be cross-referenced with Python code in `yum` and or `pkg` package managers using SystemTap or DTrace. We will need to attach to function entry and exit points to track "virtual" python backtrace and malloc call to track amount of allocated bytes. This approach is implemented in the following couple of scripts:

````` scripts/dtrace/pymalloc.d

````` scripts/stap/pymalloc.stp

!!! NOTE
We have used non-existent `foo` provider in DTrace example because like JVM, Python is linked with `-xlazyload` linker flag, so we apply same workaround to find probes that we used in [Java Virtual Machine][app/java] section. 
!!!

Arguments and local variables are also inaccessible directly by SystemTap or DTrace when program in non-native language is traced. That happens because they are executed within virtual machine which has its own representation of function frame which is different from CPU representation: languages with dynamic typing are more likely to keep local variables in a dict-like object than in a stack. These frame and dict-like objects, however, are usually implemented in C and available for dynamic tracing. All that you have to do is to provide their layout. 

Let's see how this can be done for Python 3 in Solaris and Linux. If you try to get backtrace of program interpreted by Python 3, you will probably see function named `PyEval_EvalCodeEx` which is responsible for evaluation of code object. Code object itself has type `PyCodeObject` and passed as first argument of that function. That structure has fields like `co_firstlineno`, `co_name` and `co_filename`. Last two fields not just C-style strings but kind of `PyUnicodeObject` -- an object which represents strings in Python 3. It have multiple layouts, but we rely on the simplest one: compacted ASCII strings. That may not be true for all string objects in the program, but that works fine for objects produced by the interpreter itself like code objects.

DTrace cannot recognize type information from Python libraries, but it supports `struct` definitions in the code. We will use it to provide `PyCodeObject` and `PyUnicodeObject` layouts in a separate file `pycode.h`. DTrace syntax is pretty much like C syntax, so these definitions are almost copy-and-paste from Python sources. Here is an example of DTrace scripts which trace python program execution:

````` scripts/dtrace/pycode.h

````` scripts/dtrace/pycode.d

!!! NOTE
Similar mechanism is used in so-called _ustack helpers_ in DTrace. That allows to build actual backtraces of Python or Node.JS programs when you use `jstack()` action.
!!!

SystemTap can extract type information directly from DWARF section of shared libraries so all we need to do to achieve same effect in it is to use `@cast` expression:

````` scripts/stap/pycode.stp

#### References

 * _Python_: Bugs [#4111](https://bugs.python.org/issue4111), [#13405](https://bugs.python.org/issue13405) and [#21590](https://bugs.python.org/issue21590)
 * _Perl_: [perldtrace](http://perldoc.perl.org/perldtrace.html)
 * _PHP_: [Using PHP and DTrace](http://www.php.net/manual/en/features.dtrace.dtrace.php)
 * _Ruby_: [DTrace Probes](http://ruby-doc.org/core-2.1.0/doc/dtrace_probes_rdoc.html)
 * _Erlang_: [DTrace and Erlang/OTP](http://erlang.org/doc/apps/runtime_tools/DTRACE.html)

 