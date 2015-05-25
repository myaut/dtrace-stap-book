#!/usr/sbin/dtrace -qCs

#define VFSMNTPT(vfs)   ((vfs)->vfs_vnodecovered            \
             ? stringof((vfs)->vfs_vnodecovered->v_path)    \
             : "???")
#define NBITSMINOR      32
#define MAXMIN          0xFFFFFFFF

fbt::fop_write:entry 
/args[1]->uio_resid != 0/ {
    this->dev = args[0]->v_vfsp->vfs_dev;
    @vfs[getmajor(this->dev), 
         getminor(this->dev),
         VFSMNTPT(args[0]->v_vfsp)] = sum(args[1]->uio_resid);
}

io:::start
/args[0]->b_bcount != 0 && args[0]->b_flags & B_WRITE/ {
    @bio[args[1]->dev_major,
         args[1]->dev_minor,
         args[1]->dev_statname] = sum(args[0]->b_bcount);
}

tick-1s {
    normalize(@vfs, 1024);  normalize(@bio, 1024);
    
    printf("%9s %16s %8s BDEV KB/s\n", "DEV_T", "NAME", "VFS KB/s");
    printa("%3d,%-5d %16s %8@u %@u\n", @vfs, @bio);
    
    trunc(@vfs); trunc(@bio);
}