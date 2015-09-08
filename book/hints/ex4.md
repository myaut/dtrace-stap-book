### Exercise 4

#### Part 1

If you ever traced system calls with `strace` in Linux or `truss` in Solaris, you'll probably noticed that dynamic linker `ld.so` maps shared objects into memory before program is actually run:
```
# strace /bin/ls
...
open("/lib64/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
read(3, "\177ELF\2\1\1\3\0\0\0\0\0\0\0\0\3\0>\0\1\0\0\0\0\34\2\0\0\0\0\0"..., 832) = 832
fstat(3, {st_mode=S_IFREG|0755, st_size=2107600, ...}) = 0
mmap(NULL, 3932736, PROT_READ|PROT_EXEC, MAP_PRIVATE|MAP_DENYWRITE, 3, 0) = 0x7f28fc500000
mprotect(0x7f28fc6b6000, 2097152, PROT_NONE) = 0
mmap(0x7f28fc8b6000, 24576, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x1b6000) = 0x7f28fc8b6000
mmap(0x7f28fc8bc000, 16960, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_ANONYMOUS, -1, 0) = 0x7f28fc8bc000
close(3)
```
Note that Linux `uselib` call may also being used for that.

Even if pages are already loaded into _page cache_, they might be mapped with different addresses or with different permissions (which is less likely for shared objects), so operating system need to create new memory segments for them. It also performs it lazily and only maps limited amount of pages. The rest are mapped on demand when _minor fault_ occur. That is why they occur often when new processes are spawned.

We will use `@count` aggregation and `vm.pagefault` probe to count pagefaults in SystemTap for Linux. Path to file is represented by dentry structure `$vma->vm_file->f_path->dentry` -- we will use `d_name` function to access string representation of its name.

````` scripts/stap/pfstat.stp

Speaking of Solaris, we will need to intercept `as_segat()` calls. Segments that are related to files are handled by `segvn` segment driver, so we have to compare pointer to operations table to determine if segment is corresponding to that driver.

````` scripts/dtrace/pfstat.d

When you run these scripts, you may see that most of faults are corresponding to `libc` library.

#### Part 2

As you can see from exercise text, you'll need to get allocator cache names, but they are not described in documentation to SLAB probes. To find them we will need to dive into Solaris and Linux kernel source. We seek for a name (which would be represented as a string), so we have to find allocator cache structure and fields of type `char[]` or `char*` in it. 

Let's check prototype of `kmem_cache_alloc()` function which is mentioned in probe description. First argument of it is a cache structure which we seek for. As you can see from source, it is called `kmem_cache_t`:
```
void *
kmem_cache_alloc(kmem_cache_t *cp, int kmflag)
    (from usr/src/uts/common/os/kmem.c)
```
This type is a typedefed alias for a `struct kmem_cache` which is defined in usr/src/uts/common/sys/kmem_impl.h. When you check its definition, you may find `cache_name` field -- it is obvious that this field contains name of cache.
```
struct kmem_cache {
    [...]
    char        cache_name[KMEM_CACHE_NAMELEN + 1];
    [...]
```

Of course that is not the only way to find that field. If you know how to check cache statistics statically, you should know that is is done with `::kmastat` command in `mdb` debugger. Looking at its source will reveal `kmastat_cache()` helper which prints statistics for a cache. Looking at its source may reveal accesses to `cache_name` field:
```
    mdb_printf((dfp++)->fmt, cp->cache_name);
        (from usr/src/cmd/mdb/common/modules/genunix/genunix.c).
```

Considering our findings, we may define `CACHE_NAME` macro and use it in a DTrace script:

````` scripts/dtrace/kmemstat.d

Seeking for a cache name in Linux is not that straightforward. First of all, we deal not with function boundary probes for SLAB caches, but with tapset aliases which do not provide pointers to a cache structures. Moreover, Linux has three implementations for kernel memory allocators: original SLAB, its improved version SLUB and a SLOB, compact allocator for embedded systems. SLOB is not generally used, so we will omit it.

`vm.kmem_cache_alloc` probe is defined in a `vm` tapset, so we will need to look into tapset directory `/usr/share/systemtap/tapset/linux/` to find its definition. As you can see from it, it refers either tracepoint `kmem_cache_alloc` or `kmem_cache_alloc()` kernel function. Here are source code of it:
```
void *kmem_cache_alloc(struct kmem_cache *cachep, gfp_t flags)
{
    void *ret = slab_alloc(cachep, flags, _RET_IP_);

    trace_kmem_cache_alloc(_RET_IP_, ret,
                   cachep->object_size, cachep->size, flags);

    return ret;
}
    (from mm/slab.c)
```

Note the `trace_kmem_cache_alloc` call which is actually represents invocation of the FTrace tracepoint. The same function is defined in SLUB allocator, but it uses `s` as a name of first functions argument, so we will have to use `@choose_defined` construct. Both allocators use same name for cache's structure: `struct kmem_cache`. The name is defined in that structure in files include/linux/slab_def.h and include/linux/slub_def.h:

```
struct kmem_cache {
    [...]
    const char *name;
    [...]
```

Like in Solaris, Linux shows cache statistics in `/proc/slabinfo` file. Diving into Kernel sources will reveal that `cache_name` functions is used to get cache's name and it accesses `name` field. 

Considering all this, here are an implementation of SystemTap script:

````` scripts/stap/kmemstat.stp
