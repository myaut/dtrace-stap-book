/* Подсказка: определены в /usr/lib/dtrace/io.d
inline int O_WRONLY = 1;
inline int O_RDWR = 2;
inline int O_APPEND = 8;
inline int O_CREAT = 256;
*/

this string flag_str;

syscall::openat*:entry {
    self->path = copyinstr(arg1);
    self->flags = arg2;
}

syscall::openat*:return 
{
    this->flags_str = strjoin(
        self->flags & O_WRONLY  
        ? "O_WRONLY" 
        : self->flags & O_RDWR    
            ? "O_RDWR" 
            : "O_RDONLY",
        strjoin(
            self->flags & O_APPEND  ? "|O_APPEND" : "",
            self->flags & O_CREAT   ? "|O_CREAT" : ""));

    printf("%s[%d(%d:%d)] open(\"%s\", %s) = %d\n",
                execname, pid, uid, gid, 
                self->path, this->flags_str, arg1);
}