#!/usr/sbin/dtrace -qCs

#define VFSMNTPT(vfs)   ((vfs)->vfs_vnodecovered            \
             ? stringof((vfs)->vfs_vnodecovered->v_path)    \
             : "???")
#define HASDI(bp)       (((struct buf*) bp)->b_dip != 0)
#define DEVINFO(bp)     xlate<devinfo_t*>((struct buf*) bp)

fbt::fop_read:entry 
/args[1]->uio_resid != 0/ {
    this->dev = args[0]->v_vfsp->vfs_dev;
    @vfs[getmajor(this->dev), 
         getminor(this->dev),
         VFSMNTPT(args[0]->v_vfsp)] = count();
}

io:::start
/args[0]->b_bcount != 0 && args[0]->b_flags & B_READ/ {
    @bio[args[1]->dev_major,
         args[1]->dev_minor,
         args[1]->dev_statname] = count();
}

scsi-transport-dispatch 
/arg0 != 0 && HASDI(arg0)/ {
    @scsi[DEVINFO(arg0)->dev_major,
          DEVINFO(arg0)->dev_minor,
          DEVINFO(arg0)->dev_statname] = count();
}

tick-1s {
    printf("%9s %16s %8s %8s SCSI OP/s\n", "DEV_T", "NAME", "VFS OP/s", "BDEV OP/s");
    printa("%3d,%-5d %16s %8@u %@8u %@u\n", @vfs, @bio, @scsi);
    
    trunc(@vfs); trunc(@bio); trunc(@scsi);
}
