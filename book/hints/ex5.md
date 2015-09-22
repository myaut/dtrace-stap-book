### Exercise 5

We will need to access pointer to `block_device` pointer in Linux to collect block device name and group data by it. As we know, main filesystem structure is called `super_block` which contains `s_bdev` pointer which has `struct block_device*`. SystemTap has two tapset functions, `MINOR()` and `MAJOR()` which allow to extract device number from `bd_dev` field of that structure. There is also an undocumented `bdevname()` function which is more convenient as it returns string, so we will use it. 

We will attach probes to `vfs_write()` and `vfs_read()` functions to trace filesystem operations. First argument of that functions is pointer to file of type `struct file*`. Amount of data being written or read is passed through argument `$count`. 

BIO level can be traced with `ioblock` tapset. We will do so by using its `ioblock.request` probe. It has following arguments: `bdev` -- `block_device` pointer, `size` -- amount of data in request, `rw` -- read or write flag which can be tested for equality with `BIO_READ` or `BIO_WRITE` constants.

Here is resulting `deblock.stp` script:

````` scripts/stap/deblock.stp

To trace readahead from part 2 we will need to replace `vfs_write` to `vfs_read`, `BIO_WRITE` to `BIO_READ` and get rid from amount of data in request saving into aggregation by replacing it with number of requests (which will be constant `1`).

We can use `scsi.ioentry` probe to trace SCSI operations. We can actually detect which command was used by parsing CDB buffer, but we will omit that and will trace all SCSI operations. Getting device name, however is not that easy: `request` structure which is used in SCSI stack refers to `gendisk` and `hd_struct` structures, but they won't refer to `block_device` (on contrary, `block_device` itself refers them). So we will make a small trick: there is a linked list of structures `bio` ... `biotail` which refer block device structure the same way they do in BIO probes, so we will simply copy approach from `ioblock.request` probe.

We will get `readahead.stp` script after applying all these modifications:

````` scripts/stap/readahead.stp

One can get device name with `ddi_pathname()` action or `devinfo_t` translator (which uses it indirectly) which is applied to `buf` structure. Probes from `io` provider will do it automatically by passing resulting pseudo-structure as `args[1]` argument. Aside from name, it contains minor and major device names. 

Getting device name on VFS layer, however is harder: `vfs_t` structure which describes filesystem has only device number `vfs_dev`. ZFS makes things even harder: there is intermediate layer called pool which hides block devices from filesystem layer. So we will use mountpoints as an aggregation key. We will trace filesystem operations by attaching to `fop_read()` and `fop_write()` which accept pointers to `vnode_t` of file as their first argument and pointer to `uio` structure as their second argument (it describes user request and thus contains amount of data).

Using all this we can get our `deblock.d` script:

````` scripts/dtrace/deblock.d

We will trace SCSI stack by attaching to `scsi-transport-dispatch` probe which will receive pointer to `buf` as first argument. That is very similar to probes from `io` provider except that probe doesn't apply translators on buffer. 

Other changes in `readahead.d` are similar to those that was done for SystemTap:

````` scripts/dtrace/readahead.d
