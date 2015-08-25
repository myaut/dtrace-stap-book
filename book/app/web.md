### Web applications 

Many interpreted languages that are used in Web development like Python, Perl, PHP and Ruby implement USDT probes. Some HTTP servers like Apache HTTP server (there is also an nginx fork, called nginx-dtrace) and databases such as MySQL, PostgreSQL and Berkeley DB provide them too. Let's see how that can be used to trace a real web application like Drupal CMS framework. 

!!! WARN
Despite that Apache HTTP server declares support of USDT probes, it is not supported by its build system (as you can remember, you need to perform additional steps and build extra object file). Due to that, when you build it, with `--enable-dtrace` option, you will see error message:
```
DTrace Support in the build system is not complete. Patches Welcome!
```

There is a patch written by Theo Schlossnagle that modifies build system properly, but it won't accepted. You can find fresh version of it in a bug [55793](https://bz.apache.org/bugzilla/show_bug.cgi?id=55793).

An alternative of that is to use mod\_dtrace module, but we won't discuss it in our book.
!!!

We will use Drupal with MySQL database running under Zend PHP interpreter in Apache web-server in mod_php mode. You can also use PHP-FPM, but it makes requests mapping harder as requests would be processed by different processes. In our case, without PHP-FPM, web-application and http-server would be of same context:

![image:webapp](webapp.png)

You will need to use provider name to access PHP, MySQL and Apache HTTP Server probes. Their naming convention is the same as any other USDT probe:
```
php*:::<i>probe-name</i>
mysql*:::<i>probe-name</i>
ap*:::<i>probe-name</i>
```
Same works for SystemTap: provider names are optional, but you will need to specify full path to a binary file or use its name and setup `PATH` environment variable:
```
process("httpd").mark("<i>probe__name</i>")
process("mysqld").mark("<i>probe__name</i>")
process("libphp5.so").mark("<i>probe__name</i>")
```
We will use full paths in macros in example scripts.

Here are list of arguments and names of some useful Apache probes:

---
_Action_ | _DTrace_ | _SystemTap_
Request is redirected                 | \
`internal-redirect`                     \
  * arg0 — old URI                      \
  * arg1 — new URI                    | \
`internal__redirect`                    \
  * $arg1 — old URI                     \
  * $arg2 — new URI
1,3 Request is read from socket       | \
`read-request-entry`                    \
  * arg0 — `request_rec` structure      \
  * arg1 — `conn_rec` structure       | \
`read__request__entry`                  \
  * $arg1 — `request_rec` structure     \
  * $arg2 — `conn_rec` structure
`read-request-success`                  \
  * arg0 — `request_rec` structure      \
  * arg1 — method (GET/POST/...)        \
  * arg2 — URI                          \
  * arg3 — server name                  \
  * arg4 — HTTP status                | \
`read__request__success`                \
  * $arg1 — `request_rec` structure     \
  * $arg2 — method (GET/POST/...)       \
  * $arg3 — URI                         \
  * $arg4 — server name                 \
  * $arg5 — HTTP status
`read-request-failure`                  \
  * arg0 — `request_rec` structure    | \
`read__request__failure`                \
  * $arg1 — `request_rec` structure
1,2 Request is processed              | \
`process-request-entry`                 \
  * arg0 — `request_rec` structure      \
  * arg1 — URI                        | \
`process__request__entry`               \
  * $arg1 — `request_rec` structure     \
  * $arg2 — URI
`process-request-return`                \
  * arg0 — `request_rec` structure      \
  * arg1 — URI                          \
  * arg2 — HTTP status                | \
`process__request__return`              \
  * $arg1 — `request_rec` structure     \
  * $arg2 — URI                         \
  * $arg3 — HTTP status
---

!!! WARN
When `read-request-entry`/`read__request__entry` probe is firing, `request_rec` structure fields is not yet filled.
!!!

There are also many Apache Hooks probes, but they are not providing useful arguments. 

Following table provides list of useful PHP SAPI probes:

---
_Action_ | _DTrace_ | _SystemTap_
3,1 __Request processing__
Request processing started                  |   \
`request-startup`                               \
  * arg0 — file name                            \
  * arg1 — request URI                          \
  * arg2 — request method                   |   \
`request__startup`                              \
  * $arg1 — file name                           \
  * $arg2 — request URI                         \
  * $arg3 — request method
Request processing finished                 |   \
`request-shutdown`                          >>> \
  Arguments are same as for `request-startup` | \
`request__shutdown`                         >>> \
  Arguments are same as for `request__startup`
3,1 __Compiler__
Compilation                                 |   \
`compile-file-entry`                            \
  * arg0 — source file name                     \
  * arg1 — compiled file name               |   \
`compile__file__entry`                          \
  * $arg1 — source file name                    \
  * $arg2 — compiled file name
File is compiled                            |   \
`compile-file-return`                       >>> \
  Arguments are same as for `compile-file-entry` | \
`compile__file__return`                     >>> \
  Arguments are same as for `compile__file__entry`
3,1 __Functions__
Function call                               |   \
`function-entry`                                \
  * arg0 — function name                        \
  * arg1 — file name                            \
  * arg2 — line number                          \
  * arg3 — class name                           \
  * arg4 — scope operator `::`              |   \
`function__entry`                               \
  * $arg1 — function name                       \
  * $arg2 — file name                           \
  * $arg3 — line number                         \
  * $arg4 — class name                          \
  * $arg5 — scope operator `::`
Function return                             |   \
`function-return`                           >>> \
  Arguments are same as for `function-entry`  | \
`function__return`                          >>> \
  Arguments are same as for `function__entry`
3,1 __VM execution__
Beginning of operation execution            |   \
`execute-entry`                                 \
  * arg0 — file name                            \
  * arg1 — line number                      |   \
`execute__entry`                                \
  $arg1 — file name                             \
  $arg2 — line number
Beginning of operation execution            |   \
`execute-return`                            >>> \
  * Arguments are same as for `execute-entry` | \
`execute__return`                           >>> \
  * Arguments are same as for `execute__entry`
3,1 __Errors and exceptions__
PHP error                                   |   \
`error`                                         \
  * arg0 — error message                        \
  * arg1 — file name                            \
  * arg2 — line number                      |   \
`error`                                         \
  * $arg1 — error message                       \
  * $arg2 — file name                           \
  * $arg3 — line number
Thrown exception                            |   \
`exception-thrown`                              \
  arg0 — exception class name               |   \
`exception__thrown`                             \
  arg0 — exception class name
Caught exception                            |   \
`exception-caught`                          >>> \
  * Arguments are same as for `exception-thrown` | \
`exception__caught`                         >>> \
  * Arguments are same as for `exception__thrown`
---

MySQL has wide set of probes. They are described in MySQL documentation: [5.4.1 mysqld DTrace Probe Reference](http://dev.mysql.com/doc/refman/5.7/en/dba-dtrace-mysqld-ref.html). Here are list of basic probes which allow to trace queries and connections:

---
_Action_ | _DTrace_ | _SystemTap_
1,2 Connection                           |  \
`connection-start`                          \
 *  arg0 — connection number                \
 *  arg1 — user name                        \
 *  arg2 — host name                     |  \
`connection__start`                         \
 *  $arg1 — connection number               \
 *  $arg2 — user name                       \
 *  $arg3 — host name
`connection-done`                           \
 *  arg0 — connection status                \
 *  arg1 — connection number             |  \
`connection__done`                          \
 *  $arg1 — connection status               \
 *  $arg2 — connection number
1,2 Query parsing                        |  \
`query-parse-start`                         \
 *  arg0 — query text                    |  \
`query__parse__start`                       \
 *  $arg1 — query text 
`query-parse-done`                          \
 *  arg0 — status                        |  \
`query__parse__done`                        \
 *  $arg1 —  status
1,2 Query execution                      |  \
`query-exec-start`                          \
 *  arg0 — query text                       \
 *  arg1 — connection number                \
 *  arg2 — database name                    \
 *  arg3 — user name                        \
 *  arg4 — host name                        \
 *  arg5 — source of request (cursor, procedure, etc.)   |  \
`query__exec__start`                        \
 *  $arg1 — query text                      \
 *  $arg2 — connection number               \
 *  $arg3 — database name                   \
 *  $arg4 — user name                       \
 *  $arg5 — host name                       \
 *  $arg6 — source of request (cursor, procedure, etc.)
`query-exec-done`                           \
 *  arg0 — status                        |  \
`query__exec__done`                         \
 *  $arg1 —  status
---

Here are simple tracer for PHP web application which is written on SystemTap:

````` scripts/stap/web.stp

If you run it and try to access index page of Drupal CMS with your web-browser, you will see similiar traces:
```
[httpd] read-request
[httpd] read-request    GET ??? /drupal/modules/contextual/images/gear-select.png  [status: 200]                                                                            
[httpd] process-request '/drupal/modules/contextual/images/gear-select.png'                                                                                                 
[httpd] process-request '/drupal/modules/contextual/images/gear-select.png' access-status: 304                                                                              
[httpd] read-request                                                                                                                                                        
[httpd] read-request    GET ??? /drupal/  [status: 200]                                                                                                                     
[httpd] process-request '/drupal/'                                                                                                                                          
[ PHP ] request-startup GET '/drupal/index.php' file: /usr/local/apache2/htdocs/drupal/index.php                                                                            
[ PHP ] function-entry  main file: index.php:19                                                                                                                             
[ PHP ] function-return main file: index.php:19 
…
[ PHP ] function-entry  DatabaseStatementBase::execute file: database.inc:680 
[MySQL] query-parse     'SELECT u.*, s.* FROM users u INNER JOIN sessions s ON u.uid = s.uid WHERE s.sid = 'yIR5hLWScBNAfwOby2R3FiDfDokiU456ZE-rBDsPfu0'' status: 0
[MySQL] query-exec      'SELECT u.*, s.* FROM users u INNER JOIN sessions s ON u.uid = s.uid WHERE s.sid = 'yIR5hLWScBNAfwOby2R3FiDfDokiU456ZE-rBDsPfu0'' status: 0
...
[ PHP ] request-shutdown        GET '/drupal/index.php' file: /usr/local/apache2/htdocs/drupal/index.php 
[httpd] process-request '/drupal/index.php' access-status: 200
```

As you can see from this trace, there is a request of a static image `gear-select.png` which is resulted in status 304 and a dynamic page `index.php` which eventually accesses database to check user session.

!!! WARN
You will need to restart Apache HTTP server after you start web.stp script.
!!!

Due to high amounts of script outputs, you will need to increase buffers in DTrace. The rest of script will look similiar to `web.stp`:

````` scripts/dtrace/web.d
