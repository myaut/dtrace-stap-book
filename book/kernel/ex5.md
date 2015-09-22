### Exercise 4

#### Part 1

Create two scripts: `deblock.d` and `deblock.stp` which would demonstrate effects of unaligned input output for a synchronous writes.  To do so, use aggregations to gather throughput (amount of data written) on VFS and BIO layers. Dump aggregations on terminal periodically using timer probes. Results should be grouped using name of disk device or/and mount point path.

Create filesystems to conduct experiment. For example, ext4 in CentOS:
```
# mkdir /tiger
# mkfs.ext4 /dev/sda
# mount /dev/sda /tiger
```
and ZFS in Solaris:
```
# zpool create tiger c3t0d0
```

!!! WARN
`/dev/sda` and `c3t0d0` are the names in our lab environment. Replace them with with correct ones. `/tiger` mount point, however will be used in experiment configuration files.
!!!
!!! NOTE
You can use other filesystem types, however scripts from hints and solutions section will use ext4 and ZFS. Filesystem should also have prefetching mechanisms for part 2.
!!!

Run `deblock` experiment to evaluate your scripts. 1Mb file is created in this example, and blocks of random size (which is uniformly distributed value from 512 bytes to 16 kilobytes) are written at random offsets to it. Filesystem driver has to align block size to filesystem blocks which will induce additional overheads on block layer and even extra reads. 

You can avoid effects of unaligned I/O by changing block size variator parameters like this:
```
# /opt/tsload/bin/tsexperiment -e deblock/experiment.json run   \
    -s workloads:fileio:params:block_size:randvar:min=4096  \
    -s workloads:fileio:params:block_size:randvar:max=4096
```
Block size becomes uniformly distributed in interval \[4096;4096\] which will be simply a constant value of 4 kilobytes. Re-run your script and see how workload characteristics are changed.

#### Part 2

In second part of this exercise we will evaluate filesystem prefetching or readahead mechanisms. It will significantly improve synchronous sequential read performance as operating systems will read blocks following by requested block asynchronously making it available in page cache when application will request it. 

Write `readahead.stp` and `readahead.d` scripts to see which layer is responsible for prefetching. To do so, count number of operations on three levels: Virtual File System, Block Input-Output and SCSI stack. Grouping and output are the same as in part 1.

Note that test file will be already in page cache (or ARC cache in case of ZFS) after we create them, so we will need to flush it before running an experiment. The simplest way to do that is to unmount filesystem and mount it again. I.e in Linux:
```
# umount /tiger/ ; mount /dev/sda /tiger/
```
Entire ZFS pools have to be exported-imported to destroy ARC cache.
```
# zpool export tiger ; zpool import tiger
```
You may also use `drop_caches` tunable in Linux. This should be done before each experiment run.

SimpleIO module of TSLoad workload generator will immediately start experiment after writing the file. We should create that file manually before starting it:
```
# dd if=/dev/zero of=/tiger/READAHEAD count=40960
```
And set `overwrite` option to true in experiment configuration.

Use readahead experiment to demonstrate your script. You may change sequential operations to random by changing random generator type from sequental to linear congruential generator and see how effects of readahead is changed:
```
# /opt/tsload/bin/tsexperiment -e readahead/experiment.json run \
        -s workloads:fileio:params:offset:randgen:class=lcg
```
