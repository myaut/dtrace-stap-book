#!/usr/sbin/dtrace -qCs

#define CACHE_NAME(arg)     ((kmem_cache_t*) arg)->cache_name

fbt::kmem_cache_alloc:entry {
    @allocs[CACHE_NAME(arg0)] = count();
}

fbt::kmem_cache_free:entry {
    @frees[CACHE_NAME(arg0)] = count();
}

tick-1s {
    printf("%8s %8s %s\n", "ALLOCS", "FREES", "SLAB");
    printa("%@8u %@8u %s\n", @allocs, @frees);
    
    trunc(@allocs); trunc(@frees);
}