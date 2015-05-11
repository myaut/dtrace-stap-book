#!/usr/sbin/dtrace -qCs

#pragma D option nspec=512

int specs[uint64_t];
uint64_t timestamps[uint64_t];

#define BUF_SPEC_INDEX(bp)                                       \
    ((uint64_t) bp) ^ ((struct buf*) bp)->_b_blkno._f 
#define BUF_SPECULATE(bp)                                        \
    speculate(specs[BUF_SPEC_INDEX(bp)])

#define PROBE_PRINT(probe, bp)                                   \
    printf("%-24s %p cpu%d %+llu\n", probe, bp, cpu,             \
           (unsigned long long) (timestamp -                     \
                                 timestamps[BUF_SPEC_INDEX(bp)]))

#define PROC_PRINT()                                             \
    printf("\tPROC: %d/%d %s\n", pid, tid, execname);   

#define BUF_PRINT_INFO(buf)                                      \
    printf("\tBUF flags: %s %x count: %d blkno: %d comp: ",      \
           (buf->b_flags & B_WRITE)? "W" : "R",  buf->b_flags,   \
           buf->b_bcount, buf->b_blkno);                         \
           sym((uintptr_t) buf->b_iodone); printf("\n")

#define DEV_PRINT_INFO(dev)                                      \
    printf("\tDEV %d,%d %s\n", dev->dev_major, dev->dev_minor,   \
           dev->dev_name);

#define FILE_PRINT_INFO(file)                                    \
    printf("\tFILE %s+%d\n", file->fi_pathname, file->fi_offset);     

#define PTR_TO_SCSIPKT(pkt) ((struct scsi_pkt*) pkt)
#define SCSIPKT_TO_BP(pkt)  ((struct buf*) PTR_TO_SCSIPKT(pkt)->pkt_private)

#define SCSIPKT_PRINT_INFO(pkt)                                  \
    printf("\tSCSI PKT flags: %x state: %x comp: ",              \
            pkt->pkt_flags, pkt->pkt_state);                     \
            sym((uintptr_t) pkt->pkt_comp); printf("\n")

io:::start {
    specs[BUF_SPEC_INDEX(arg0)] = speculation();
    timestamps[BUF_SPEC_INDEX(arg0)] = timestamp;
}

io:::start {
    BUF_SPECULATE(arg0);
    
    printf("---------------------\n");
    PROBE_PRINT("io-start", arg0);
    PROC_PRINT();
    BUF_PRINT_INFO(args[0]);
    DEV_PRINT_INFO(args[1]);
    FILE_PRINT_INFO(args[2]);
}

*sd_initpkt_for_buf:entry {
    self->bp = arg0;
}

*sd_initpkt_for_buf:return
/arg1 != 0/ {
    BUF_SPECULATE(self->bp);
    PROBE_PRINT("ALLOCATION FAILED", self->bp);
}

*sd_initpkt_for_buf:return
/arg1 != 0/ {
    commit(specs[BUF_SPEC_INDEX(self->bp)]);
}

*sdstrategy:entry {
    BUF_SPECULATE(arg0);
    PROBE_PRINT(probefunc, arg0);
}

*sd_add_buf_to_waitq:entry {
    BUF_SPECULATE(arg1);
    PROBE_PRINT(probefunc, arg1);
}

scsi-transport-dispatch {
    BUF_SPECULATE(arg0);
    PROBE_PRINT(probename, arg0);
}

scsi_transport:entry {
    this->bpp = (uint64_t) SCSIPKT_TO_BP(arg0);

    BUF_SPECULATE(this->bpp);
    PROBE_PRINT(probefunc, this->bpp);
    SCSIPKT_PRINT_INFO(PTR_TO_SCSIPKT(arg0));
}

*sdintr:entry {
    self->bpp = (uint64_t) SCSIPKT_TO_BP(arg0);
    
    BUF_SPECULATE(self->bpp);
    PROBE_PRINT(probefunc, self->bpp);
    SCSIPKT_PRINT_INFO(PTR_TO_SCSIPKT(arg0));
}

io:::done {
    BUF_SPECULATE(arg0);
    PROBE_PRINT("io-done", arg0);
    BUF_PRINT_INFO(args[0]);
}

io:::done {
    commit(specs[BUF_SPEC_INDEX(arg0)]);
    specs[BUF_SPEC_INDEX(arg0)] = 0;
}
