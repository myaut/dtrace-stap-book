### [__index__:virtual memory] Virtual memory

Consider the following C program which will be translated into assembler:
```
char msg[] = "Hallo, world";	// mov %edi, $224cc
msg[1] += 4;					// add (%edi), $4
```
When single instance of that program is running, it will work as expected, message will become "Hello, world". But what will happen if two instances of program will be run simultaneously? Since compiler have used absolute addressing, second program may have been overwritten data of first instance of a program, making it "Hillo, world!" (actually, before that, program loader should load original message "Hallo, world" back). So multiprocessing creates two problems: same addresses of different processes shouldn't point to same physical memory cell and processes should be disallowed to write to memory that doesn't belong to them. _Virtual memory_ is an answer to that problems.

Modern virtual memory mechanisms are based on _page addressing_: all physical memory is divided to a pages of a small size (4 kb in x86). Processes are exist in a virtual address space where each subset of addresses, say `[BASE;BASE+PAGESIZE)`, maps to a single page. List of such mappings is maintained as _page table_. Modern CPUs also provide support for _huge pages_ (Linux) or _large pages_ (Solaris) which may be megabytes or even gigabyte in size. Speaking of our previous example, kernel _binary format loader_ will set up a virtual address space for our program, copying all data to a new locations in physical memory:

![image:pagetable](pagetable.png)

When second instance of a program will start, new process with separate address space will be created, thus making independent copy of process data, including "Hallo, world" message, but with same addresses. When process (actually its thread or task) is dispatched onto CPU, address of its page table is written to a special register (like CR3 on x86), so only it may access its data. All address translations are performed by _Memory Management Unit_ in CPU and are transparent for it.

[__index__:segments] From the process point of view, pages are grouped into _segments_ which constitute _address space_:

![image:pas](pas.png)

New address spaces are created as a result of `execve()` system call. When it is finished, new address space constitutes from four segments: _text_ segment contains program code, _data_ segment contains program data. Binary loader also creates two special segments: _heap_ for dynamically allocated memory and _stack_ for program stack. Process arguments and environment are also initially put onto stack. Than, kernel runs process interpreter `ld.so`, which actually a dynamic linker. That linker searches for libraries for a process such as standard C library `libc.so` and calls `mmap()` to load text and data sections of that libraries. 

[__index__:anonymous memory] When you try to allocate memory using `malloc()`, standard C library may increase heap using `brk()` or `sbrk()` system call. Program may also use `mmap()` calls to map files into memory. If no file is passed to `mmap()` call, then it will create special memory segment called an _anonymous memory_. Such memory segment may be used for memory allocators, independent from main process heap.

You can check address space of a process with `pmap` program or by viewing `/proc/PID/mapping` file on Linux. 

Let's for example see, how memory is dynamically allocated by calling `malloc()` with relatively large value. I used Python 2 `range(10000)` built-in which creates list with 10000 numbers.

[__index__:vm (tapset, SystemTap)] SystemTap provides corresponding syscalls via tapset `vm`:
```
# stap -d $(which python) --ldd -e '
	probe vm.brk, vm.mmap, vm.munmap { 
		printf("%8s %s/%d %p %d\n", 
			name, execname(), pid(), address, length); 
		print_ubacktrace();
	}' -c 'python -c "range(10000)"' 
```

Solaris doesn't have such tapset, but these operations are performed using `as_map()` and `as_unmap()` kernel functions:
```
# dtrace -qn '
	as_map:entry, as_unmap:entry { 
		printf("%8s %s/%d %p %d\n", 
			probefunc, execname, pid, arg1, arg2);
		ustack();
	}'  
# python -c "import time; range(10000); time.sleep(2)"	
```

After running both of these scripts, you will see, that lot's of `brk()` calls are caused by `builtin_range()` function in Python. 

Process address space is kept in `mm_struct` in Linux and in `as_t` structure in Solaris:

![image:mm](linux/mm.png)

Each memory segment is represented by instance of `vm_area_struct` structure which has two addresses: `vm_start` which points to the beginning of a segment and `vm_end` which points to the end of the segment. Kernel maintains two lists of segments: linear double-linked list of segments (sorted by their addresses) starting with `mmap` pointer in `mm_struct` with `vm_next` and `vm_prev` pointers, another list is a red-black tree built with `mm_rb` as root and `vm_rb` as node. 

Segments may be mapped files, so they have non-NULL value of `vm_file` pointing to a `file`. Each `file` has an `address_space` which contains all pages of a file in a `page_tree` in a `address_space` object. This object also references `host` inode of a file and all mappings corresponding to that file through linear and non-linear lists, thus making all mappings of a file shared. Another option for mapping is anonymous memory -- its data is kept in `anon_vma` structure. Every segment has a `vm_mm` pointer which refers `mm_struct` to which it belongs. 

`mm_struct` alone contains other useful information, such as base addresses of entire address space `mmap_base`, addresses of a stack, heap, data and text segments, etc. Linux also caches memory statistics for a process in `rss_stat` field of `mm_struct` which can be pretty-printed with `proc_mem*` functions in SystemTap:
```
# stap -e '
	probe vm.brk, vm.mmap { 
		printf("%8s %d %s\n", name, pid(), proc_mem_string()); 
	}' -c 'python -c "range(10000)"' 
```

In Solaris `as_t` structure accessible through `p_as` field of process and keeps all segments in AVL tree where `a_segtree` is a root node and `s_tree` is a nodes embedded to a segment:

![image:as](solaris/as.png)

Each segment has backward link to address space `s_as`, `s_base` as base address of a segment and `s_size` as its size. Solaris uses so-called _segment drivers_ to distinguish one type of a segment to another, so it provides table of operations through `s_ops` field and private data through `s_data` field. One of the segment drivers is _segvn_ driver which handles mmapped segments of memory both from files and anonymous, which keep their data in `segvn_data` structure which holds two pointers: `vp` to file's vnode and `amp` for a map of anonymous memory. 

Some memory will be consumed by a process indirectly. For example, when application transfers a packet through the network or writes data to a file on /tmp filesystem, data is buffered by Kernel, but that memory is not mapped to a process. To do so, Kernel uses various in-kernel memory allocators and maintains _kernel address space_. 

#### [__index__:page fault] Page fault

As we mentioned before, when program accesses memory, memory management unit takes address, finds an entry in a page table and gets physical address. That entry, however, may not exist -- in that case CPU will raise an exception called a _page fault_. There are three types of page faults that may happen:
 * _Minor_ page fault occurs when page table entry should exist, but corresponding page wasn't allocated or page table entry wasn't created. For example, Linux and Solaris do not allocate mmapped pages immediately, but wait until first page access which causes minor page faults.
 * _Major_ page fault requires reading from disk. It may be caused by accessing memory-mapped file or when process memory was paged-out onto disk swap.
 * _Invalid_ page fault occur when application access memory at invalid address or when segment permissions forbid such access (for example writing into text segment, which is usually disallowed). In this case operating system may raise `SIGSEGV` signal. A special case of invalid page faults is _copy-on-write_ fault which happens when forked process tries to write to a parent's memory. In this case, OS copies page and sets up a new mapping for forked process.

Page faults are considered harmful because they interrupt normal process execution, so there are various system calls such as `mlock()`, `madvise()` which allow to flag memory areas to reduce memory faults. I.e. `mlock()` should guarantee page allocation, so minor fault won't occur for that memory area. If page faults occurs in a kernel address space, it will lead to kernel oops or panic.

You can trace page faults in Linux by attaching to `vm.pagefault.return` probe. It has `fault_type` variable which is a bitmask of a fault type. RedHat-like kernels also have `mm_anon_*` and `mm_filemap_*` probes. Page faults is also presented to a perf subsystem. In Solaris all virtual memory events including page faults are available in `vminfo` provider:

---
__Type__ | __DTrace__ | __SystemTap__
_Any_ | `vminfo::as_fault` | `perf.sw.page_faults`
_Minor_ |  | `perf.sw.page_faults_min`
_Major_ | `vminfo:::maj_fault` usually followed by `vminfo::pgin` | `perf.sw.page_faults_maj`
_Invalid_ | `vminfo:::cow_fault` for copy-on-write faults \
			`vminfo:::prot_fault` for invalid permissions or address | See notes below
---

!!! NOTE
Linux doesn't have distinct probe for invalid page fault -- these situations are handled by architecture-specific function `do_page_fault()`. They are handled by family of `bad_area*()` functions on x86 architecture, so you can attach to them:
```
# stap -e '
	probe kernel.function("bad_area*") { 
		printf("%s pid: %d error_code: %d addr: %p\n", 
			probefunc(), pid(), $error_code, $address); 
	} '
```
!!!

!!! NOTE
By default `perf` probe fires after multiple events, because it is sampler. To alter that behaviour, you should use `.sample(1)` which will fire on any event, but that requires to pass `perf` probes in raw form, i.e.:
```
	perf.type(1).config(2).sample(1)
```
You can check actual values for type and config in `/usr/share/systemtap/linux/perf.stp` tapset. See also: [perf syntax][principles/profiling#perf] in Profiling section of this book.
!!!

Page fault is handled by `as_fault()` function in Solaris:
```
faultcode_t as_fault(struct hat *hat, struct as *as, 
					 caddr_t addr, size_t size, 	
					 enum fault_type type, enum seg_rw rw);
```
This function calls `as_segat` to determine segment to which fault address belongs, providing `struct seg*` as a return value. When no segment may be found due to invalid fault, it returns NULL. 

Let's write simple tracer for these two functions. It also prints `amp` address and path of vnode for segvn driver:

````` scripts/dtrace/pagefault.d

Here is an example of a page fault traced by this script:
```
<b>as_fault</b> pid: 3408 as: 30003d2dd00
	addr: d2000 size: 1 flags: F_PROT|S_WRITE 
	[c0000:d4000] rwxu
	vn: /usr/bin/bash
	amp: 30008ae4f78:0
```
It was most likely a data segment of a `/usr/bin/bash` binary (because it has rights `rwxu`), while type of the fault is `F_PROT` which means invalid access right which makes it copy-on-write fault. 

If you run a script for a process which allocates and initializes large amount of memory, you'll see lots of minor faults (identifiable by `F_INVAL`) with addresses which are go sequentially:
```
<b>as_fault</b> pid: 987 as: ffffc10008fc6110
	addr: 81f8000 size: 1 flags: F_INVAL|S_WRITE 
	[8062000:a782000] rw-u
<b>as_fault</b> pid: 987 as: ffffc10008fc6110
	addr: 81f9000 size: 1 flags: F_INVAL|S_WRITE 
	[8062000:a782000] rw-u
<b>as_fault</b> pid: 987 as: ffffc10008fc6110
	addr: 81fa000 size: 1 flags: F_INVAL|S_WRITE 
	[8062000:a782000] rw-u
```
Like we mentioned before, when application allocates memory, pages are not necessarily created. So when process touches that memory first time, page fault occurs and actual page allocation is performed.

Similarly, all pagefaults are handled by `handle_mm_fault()` function in Linux:
```
int handle_mm_fault(struct mm_struct *mm, 
					struct vm_area_struct *vma,
					unsigned long address, unsigned int flags);
```

SystemTap provides a wrapper for it: `vm.pagefault` which we will use to write pagefault tracer script for Linux:

````` scripts/stap/pagefault.stp

Here is an example of its output:
```
<b>vm.pagefault</b> pid: 1247 mm: 0xdf8bcc80
		addr: 0xb7703000 flags: WRITE
		VMA [0xb7703000:0xb7709000]
		prot: rw-- may: rwx- flags: VM_ACCOUNT
		amp: 0xdc62ca54
			=> pid: 1247 pf: MINOR
```

!!! WARN
`vma_flags` are not stable and change from version to version. This script contains values according to CentOS 7. Check `include/linux/mm.h` for details.
!!!

#### [__index__:memory allocator] Kernel allocator

Virtual memory is distributed between applications and kernel by a subsystem which called _kernel allocator_. It may be used both for applications and for internal kernel buffers such as ethernet packets, block input-output buffers, etc. 

Lower layer of the kernel allocator is a _page allocator_. It maintains lists of _free pages_ which are immediately available to consumers, _cache pages_ which are cached filesystem data and may be easily evicted and _used pages_ that has to be reclaimed thus being writing on disk swap device. Page allocation is performed by `page_create_va()` function in Solaris which provides `page-get` and `page-get-page` static probes:
```
# dtrace -qn '
	page-get* { 
		printf("PAGE lgrp: %p mnode: %d bin: %x flags: %x\n", 
			arg0, arg1, arg2, arg3); 
	}'
```

!!! WARN
Solaris 11.1 introduced new allocator infrastructure called _VM2_. Information about it is not publicly available, so it is out of scope of our book. 
!!!

Linux page allocator interface consists of `alloc_pages*()` family of functions and `__get_free_pages()` helper. They have `mm_page_alloc` tracepoint which allows us to trace it:
```
# stap -e '
	probe kernel.trace("mm_page_alloc") { 
		printf("PAGE %p order: %x flags: %x migrate: %d\n",
				$page, $order, $gfp_flags, $migratetype); 
	}'
```

For most kernel objects granularity of a single page (4 or 8 kilobytes usually) is too high, because most structures have varying size. On the other hand, implementing a classical heap allocator is not very effective considering the fact, that kernel performs many allocations for an object of same size. To solve that problem, a _SLAB allocator_ (which we sometimes will refer to as _kmem allocator_) was implemented in Solaris. SLAB allocator takes one or more pages, splits it into a buffers of a smaller sizes as shown on picture:

![image:kmem](kmem.png)

Modern SLAB allocators may have various enhancements like per-cpu slabs, SLUB allocator in Linux. Moreover, cache object is not necessarily created in SLAB allocators -- objects of generic sizes may be allocated through function like `kmalloc()` in Linux or `kmem_alloc` in Solaris which will pick cache based on a size, such as `size-32` cache in Linux or `kmem_magazine_32` in Solaris. You can check overall SLAB statistics with `/proc/slabinfo` file in Linux, `::kmastat` mdb command in Solaris or by using KStat: `kstat -m unix -c kmem_cache`. 

Here are list of the probes related to kernel allocator:

---
__Object__ | __Action__ | __DTrace__ | __SystemTap__
Block of an unspecified size | alloc | \
`fbt::kmem_alloc:entry` and `fbt::kmem_zalloc:entry` \
 * `arg0` -- size of the block \
 * `arg1` -- flags 		| \
`vm.kmalloc` and `vm.kmalloc_node` \
 * `caller_function` -- address of caller function \
 * `bytes_req` -- requested amount of bytes \
 * `bytes_alloc` -- size of allocated buffer \
 * `gfp_flags` and `gfp_flags_str` -- allocation flags \
 * `ptr` -- pointer to an allocated block
Block of an unspecified size | free | \
`fbt::kmem_free:entry` \
 * `arg0` -- pointer to the block \
 * `arg1` -- size of the block	| \
`vm.kfree` \
 * `caller_function` -- address of caller function \
 * `ptr` -- pointer to an allocated block
Block from pre-defined cache | alloc | \
`fbt::kmem_cache_alloc:entry` \
 * `arg0` -- pointer to `kmem_cache_t` \
 * `arg1` -- flags | \
`vm.kmem_cache_alloc` and \
`vm.kmem_cache_alloc_node` \
Same params as `vm.kmalloc`
Block from pre-defined cache | free | \
`fbt::kmem_cache_free:entry` \
 * `arg0` -- pointer to `kmem_cache_t` \
 * `arg1` -- pointer to a buffer | \
`vm.kmem_cache_free` and \
Same params as `vm.kfree`
---

Note that SystemTap probes are based on a tracepoints and provided by `vm` tapset.

On the other hand, when kernel needs to perform large allocations which are performed rarely, different subsystems are used: _vmalloc_ in Linux, or _vmem_ in Solaris (which is used by _kmem_ SLAB allocator). Solaris also have segment drivers such as _segkmem_, _segkpm_, etc. 