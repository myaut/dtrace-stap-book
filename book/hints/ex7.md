### Exercise 7

Nature of solution of this exercise depends on your Apache and PHP configuration. In our case (as described in [lab description][lab/web]), PHP was built as Apache HTTPD module (by using `--with-apxs2` option of `configure`-script), so all PHP code will be executed in a context of Apache worker, so we can safely use Thread-Local variables. If PHP was deployed with PHP-FPM, things would be more complicated.

So we will need to use `process-request-entry` probe to get URI of request and pair of probes `function-entry`/`function-entry` to measure execution time of a function. Since name of a method is passed in multiple probe arguments, we will have to use string concatenation. Like in many other exercises, we will use aggregations to collect statistics. Note that you can use PHP probe `request-startup` instead of `process-request-entry`.

As you could remember from a [profiling][principles/profiling] section of tracing principles, generally you shouldn't measure execution time of a function by tracing entry and exit points of it. However, PHP is an interpreted language, so it has lesser relative overheads of tracing because execution of its opcodes is slower than for the real processor (unless you are using some precompiler to machine language like HHVM) and we can afford full-tracing of it.

Here are resulting implementations of scripts for SystemTap and DTrace:

````` scripts/stap/topphp.stp
````` scripts/dtrace/topphp.d
