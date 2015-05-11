struct stat_info {
    long long st_size;
};

translator struct stat_info < uintptr_t s > {
    st_size = * ((long long*) copyin(s + offsetof(struct stat64_32, st_size),
                                     sizeof (long long)));
};

syscall::fstatat64:entry
{
        self->filename = copyinstr(arg1);
        self->statptr = arg2;
}

syscall::fstatat64:return
{
        printf("STAT %s size: %d\n", self->filename, 
               xlate < struct stat_info* > (self->statptr)->st_size);
}

