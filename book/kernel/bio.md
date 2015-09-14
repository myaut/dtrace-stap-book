### Block Input-Output

When request is handled by Virtual File System, and if it needs to be handled by underlying block device, VFS creates a request to Block Input-Output subsystem. Operating system in this case either fetches new page from a disk to a page cache or writes dirty page onto disk. Disks are usually referred to as _block devices_ because you can access them by using blocks of fixed size: 512 bytes which is disk sector (not to mention disks with advanced format or SSDs). On the other hand, _character devices_ like terminal emulator pass data byte by byte while _network devices_ might have any length of network packet.

BIO top layer is traceable through `io` provider in DTrace:
```
# dtrace -qn '
    io:::start 
    /args[0]->b_flags & B_READ/ { 
    printf("io dev: %s file: %s blkno: %u count: %d \n", 
        args[1]->dev_pathname, args[2]->fi_pathname, 
        args[0]->b_lblkno, args[0]->b_bcount); 
    }' -c "dd if=/dev/dsk/c2t0d1p0 of=/dev/null count=10" 
```
If you check function name of that probe, you may see that it is handled by `bdev_strategy()` kernel function which has only one argument of type `struct buf`. That buffer represents a single request to a block subsystem and passed as `arg0` to `io:::start` probe and then translated to a `bufinfo_t` structure which is considered stable. DTrace also supplies information about block device and file name in `args[1]` and `args[2]`. 

Linux has similar architecture: it has `struct bio` which represents single request to block subsystem and `generic_make_request()` function (which, however, has alternatives) which passes `bio` structure to device queues. SystemTap tapset `ioblock` provides access to BIO probes:
```
# stap -e '
    probe ioblock.request { 
        if(bio_rw_num(rw) != BIO_READ) 
            next; 
        printf("io dev: %s inode: %d blkno: %u count: %d \n", 
            devname, ino, sector, size); 
    }' -c "dd if=/dev/sda of=/dev/null count=10"
```
In these examples we have traced only read requests. 

Here are description of `buf` structure from Solaris and `bio` structure from Linux:

---
__Field description__ | `bufinfo_t` translator or `struct buf` | `struct bio`
Request flags | `b_flags` | `bi_flags`
Read or write | flags `B_WRITE`, `B_READ` in `b_flags` | `bi_rw`, see also functions `bio_rw_num()` and `bio_rw_str()`
Number of bytes | `b_bcount` | `bi_size`
Id of block | `b_blkno`, `b_lblkno` | `bi_sector`
Request finish callback | `b_iodone` | `bi_end_io`
Device identifiers | `b_edev`, `b_dip` | `bi_bdev`
Pointer to data | `b_addr` or `b_pages` (only in `buf` when `B_PAGEIO` flag is set) |1,2 See note below
Pointer to file descriptor | `b_file` (only in `buf`)
---

!!! NOTE
`struct bio` in Linux contains table `bi_io_vec`, where each element contains pointer to a page `bv_page`, length of data `bv_len` and offset inside page `bv_offset`. Field `bi_vcnt` shows how many structures of that type is in vector while current index is kept in `bi_idx`.

Every `bio` structure can contain many files related to it (i.e. when I/O scheduler merges requests for adjacent pages). You can find file inode by accessing `bv_page` which points to a page-cache page, which will refer `inode` through its mapping.
!!!

When _BIO request_ is created it is passed to scheduler which re-orders requests in a way which will require fewer movement of disk heads (this improves HDD access time). This subystem plays important role in Linux which implements a lot of different schedulers, including _CFQ_ (used by default in many cases), _Deadline_ and _NOOP_ (doesn't perform scheduling at all). They are traceable with `ioscheduler` tapset. Solaris doesn't have centralized place for that: ZFS uses _VDEV queue_ mechanism, while the only unifying algorithm is _lift sorter_ which is implemented in `sd_add_buf_to_waitq()`.

After scheduling BIO layer passes request to a device level:

![image:bio](bio.png)

Both Solaris and Linux use SCSI protocol as unified way to represent low-level device access. SCSI devices can be stacked, i.e. with _device mapper_ in Linux or _MPxIO_ in Solaris, but we will have only single layer in our examples. In any case, this subsystem is called _SCSI stack_. All requests in SCSI stack are translated to SCSI packets (which can be translated to ATA commands or passed as is to SAS devices). SCSI packet is handled in a several steps:

---
__Action__ | __Solaris__ | __Linux__
New instance of SCSI packet is created | `scsi_init_pkt()` | `scsi.ioentry`
SCSI packet is dispatched on queue | `sd_add_buf_to_waitq()` | `scsi.iodispatching`
SCSI packet is passed to low-level driver | `sdt::scsi-transport-dispatch` >>> \
                                            `scsi_transport()`  | `scsi.ioexecute`
Low-level driver generates interrupt when SCSI packet is finished | `sd_return_command()` | `scsi.iocompleted` >>>\
                                                                                            `scsi.iodone`
---

!!! WARN
Probe `scsi.ioexecute` can be not fired for all SCSI packets: usually bus or disk driver puts request to internal queue and processes it independently from SCSI stack.
!!!

!!! NOTE
We have used Solaris functions starting from `sd` prefix in this example. They are from `sd` driver which represents SCSI disk. There is also `ssd` driver which is used for FC disks -- it is based on `sd` driver, but all functions in it are using `ssd` prefix, i.e. `ssd_return_command`.
!!!

![image:solaris-bio](solaris/bio.png)

In Solaris each SCSI _LUN_ has a corresponding `sd_lun` structure which keeps queue of buffers in doubly-linked list referenced by `un_waitq_headp` and `un_waitq_tailp` pointers. When new command is passed to SCSI stack, `un_ncmds_in_driver` is increased and when packet is dispatched to transport, `un_ncmds_in_transport` is increased. They are decreased when SCSI packet is discarded or when it was successfully processed and interrupt is fired to notify OS about that. SCSI stack uses `b_private` field to keep `sd_xbuf` structure that keeps reference to SCSI packet through `xb_pktp` pointer.

Following script traces block I/O layer and SCSI stack (`sd` driver in particular) in Solaris:

````` scripts/dtrace/sdtrace.d

It saves history of all I/O stages into a [speculation][lang/print#speculation] which is committed when operation is finished. Note that due to the fact that speculation has one buffer per processor output may be garbled when interrupt was delivered to a processor other than processor that initiated request and `sdintr` is called on it. 

Here is an example output for script:
```
<b>io-start</b>                 ffffc100040c4300 cpu0 2261
        PROC: 1215/1 dd
        BUF flags: R 200061 count: 512 blkno: 0 comp:   0x0                                               
        DEV 208,192 sd
        FILE <none>+-1
<b>sd_add_buf_to_waitq</b>      ffffc100040c4300 cpu0 11549
<b>scsi-transport-dispatch</b>  ffffc100040c4300 cpu0 18332
<b>scsi_transport</b>           ffffc100040c4300 cpu0 21136
        SCSI PKT flags: 14000 state: 0 comp:   sd`sdintr                                         
<b>sdintr</b>                   ffffc100040c4300 cpu0 565121
        SCSI PKT flags: 14000 state: 1f comp:   sd`sdintr                                         
<b>io-done</b>                  ffffc100040c4300 cpu0 597642
        BUF flags: R 2200061 count: 512 blkno: 0 comp:   0x0
```

Each stage of request (marked bold) contains its name, address of `buf` pointer and time since request creation in nanoseconds. In our case largest difference is between `scsi_transport` and `sdintr` which is about half a second. It can be simply explained: actual I/O was performed between these stages, and it is slower than processor operations. 

SCSI stack also uses callback mechanism to notify request initiators when it is finished. In our case lower-level driver had used `sdintr` callback while `b_iodone` field wasn't filled. It is more likely that caller used `biowait()` routine to wait for request completion. 

Like we said before, Linux has intermediate layer called a scheduler which can re-order requests. Due to that, BIO layer maintains generic layer of block device queues which are represented by `struct request_queue` which holds requests as `struct request` instances:

![image:linux-bio](linux/bio.png)

Each request may have multiple `bio` requests which are kept as linked list. New requests are submitted through `blk_queue_bio()` kernel function which will either create a new `request` using `get_request()` function for it or merge it with already existing `request`.

Here are example script for Linux which traces BIO layer and SCSI stack:

````` scripts/stap/scsitrace.stp

Script example outputs are shown below:

```
<b>kernel.function("get_request@block/blk-core.c:1074").return</b> 0xffff880039ff1500 0xffff88001d8fea00 cpu0 4490
        PROC: 16668/16674 tsexperiment
        BUF flags: R f000000000000001 count: 4096 blkno: 779728 comp: end_bio_bh_io_sync
        DEV 8,0 INO 0
<b>ioscheduler.elv_add_request</b> 0xffff880039ff1500 0xffff88001d8fea00 cpu0 15830
        DEV 8,0
<b>scsi.ioentry</b>             0xffff880039ff1500 0xffff88001d8fea00 cpu0 19847
<b>scsi.iodispatching</b>       0xffff880039ff1500 0xffff88001d8fea00 cpu0 25744
        SCSI DEV 2:0:0:0 RUNNING
        SCSI PKT flags: 122c8000 comp: 0x0
<b>scsi.iodispatching</b>       0xffff880039ff1500 0xffff88001d8fea00 cpu0 29882
<b>scsi.iodone</b>              0xffff880039ff1500 0xffff88001d8fea00 cpu1 4368018
<b>scsi.iocompleted</b>         0xffff880039ff1500 0xffff88001d8fea00 cpu0 4458073
<b>ioblock.end</b>              0xffff880039ff1500 cpu0 1431980041275998676
```

Unlike Solaris, it shows to pointers for each stage: one for `bio` structure and one for `request`. Note that we didn't use `ioblock.request` in our example. That is because we wanted to distinguish merged and alone requests which can be done only with function boundary tracing.

!!! NOTE
Linux 3.13 introduced a new mechanism for block device queues called _blk-mq_ (_Multi-Queue Block IO_). It is not covered in this book.
!!!