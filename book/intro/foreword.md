### Foreword

While I was working on my bachelor thesis, I discovered that code analysis task is a key step on the path towards solving software problems: aborts and coredumps, excessive (or unreasonably small) resource consumptions, etc. It was devoted to microkernel architecture, and when I found it inadequately documented, I had to dive deep down to their sources.

After that, I started to apply code reading on my work, because sources always have most actual and full information than user documentation. Sources better explain origin of an error than documentation. For example, take a look at [UFS documentation for Solaris 10](http://docs.oracle.com/cd/E23823_01/html/816-5166/newfs-1m.html):

> _-b bsize_
	The logical block size of the file system in bytes, either 4096 or 8192. The default is 8192. 	The sun4u architecture does not support the 4096 block size.

Real condition that describes block size limits in UFS is a bit more complex:

```
	928    if (fsp->fs_bsize > MAXBSIZE || fsp->fs_frag > MAXFRAG ||
	929        fsp->fs_bsize < sizeof (struct fs) || 
						fsp->fs_bsize < PAGESIZE) {
	930           error = EINVAL; /* also needs translation */
	931           goto out;
	932    }
```

[](http://fxr.watson.org/fxr/source/common/fs/ufs/ufs_vfsops.c?v=OPENSOLARIS#L928)

So, more accurate condition that applies to all architectures may be described as: block size should be greater or equal page size, but not exceed 8192 bytes (`MAXBSIZE` macro) and also be larger than superblock. I have to admit, that sometimes I was too hasty to look into code and ignored clues that documentation provides, but in most cases source code analysis approach paid off, especially in hard ones. 

Information extraction from source code alone is called _static code analysis_. This method is not sufficient, because you cannot look into source of highly-universal system like Linux Kernel without having in mind what requests it will process. Otherwise, we would have to process all code branches, but that dramatically increases complexity of code analysis. Because of that, you have to run experiments sometimes and perform _dynamic code analysis_. Through dynamic analysis you will cut out unused code paths and improve your understanding of a program.

While I was working on my thesis, I used Bochs simulator which can generated giant traces: one line per assembly instructions. Fortunately, modern operating systems have much more flexible tools: _dynamic instrumentation tools_, and that is the topic of this book. 

I wrote first useful DTrace script for the request in which customer encountered the following panic:

```
	unix: [ID 428783 kern.notice] vn_rele: vnode ref count 0
```

As you can see from the message, _reference counter_ decreases one more time (for example, if you closed file twice). Of course, if you call `close()` twice, that won't cause system panic, so we have to deal with more specific _race condition_ or a simple bug when `vn_rele()` is called twice. To unveil that issue, I had to write DTrace script, that traced `close()` and `vn_rele()` calls (and also some socket stuff).

While I was getting familiar with Linux Kernel, I used DTrace competitor from Linux World -- SystemTap. I began preparation of small workshop about DTrace and SystemTap in 2011, but I decided to add comments to each slide for my workshop. The amount of comments was growing: I prepared introduction, chapter about script languages in DTrace and SystemTap and description of process management in Linux and Solaris with _dumptask_ scripts. But amount of time that I spend to prepare "process management" topic had scared me, and I decided that I couldn't write all topics about OS kernel architecture that I planned in the beginning, so I stopped writing this book.

I returned to it in 2013. At the time, I was actively deconstructing CFS scheduler in Linux, so it made easier to write next architecture topic: "process scheduler". I had some experience with ZFS internals, so writing topics about block input-output was easy too. Eventually, I got interest in web application performance -- that gave ground to fifth chapter of this book. In the end of 2013 draft of this book was prepared. Unfortunately, editing took more than year, and another year -- translation. 

Two specialists in the area of Solaris internals and DTrace: Jim Mauro and Brendan Gregg, had published a book "DTrace Dynamic Tracing in Oracle® Solaris, Mac OS X, and FreeBSD" in 2011. It has huge volume (more than thousand pages), and excellent description of basic performance and computer architecture principles and how they reflected in DTrace tracing capabilities. That book has a lot of one-liners that can be copied to the terminal and start collecting data immediately. In our book we will concentrate our efforts in diving into applications and kernel code and how it can be traced.

Book goals changed while it was written too that lead to inconsistencies. Originally it was just with comments, I put everything looking like documentation as a links, but modules 4 and 5 have tables with probe names and its arguments. While book was written, SystemTap was rapidly growing, Linux kernel is changing fast and Solaris became proprietary so it is hard to maintain example compatibilities for several versions simultaneously. I've updated examples for CentOS 7 and Solaris 11.2, but it'll probably break compatibility with older versions.

Send me your feedback to `myautneko+dtrace_stap@gmail.com`.

#### Acknowledgements 

I want to thank my advisor, Boris Timchenko, who gave me direction in the world of Computer Science and whose influence was probably highest motivation to write this book. He is probably first man who said word _trace_ in my life. Thanks to Sergey Klimenkov and Dmitry Sheshukov, my former supervisors at [Tune-IT](http://www.tune-it.ru/en) who were very supportive during preparation of that book. It will also won't happen without Tune-IT demo equipment which were used to try examples and lab assignments. Sergey is also an expert in Solaris architecture, he is teaching Solaris Internals at Tune-IT education centre, and I was one of his students there.

Thanks DTrace & SystemTap community for creating such great instruments, especially Brendan Gregg, who is first man who tamed power of these tools. Nan Xiao is a great person who edited this book. 

And finally, this book won't happen without my parents, who inspired my to always learn new. 
