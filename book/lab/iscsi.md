### iSCSI

We will need to use SCSI device so we can fully trace it in [exercise 5][kernel/ex5]. Xen hypervisor supports SCSI emulation, but only by emulating outdated _LSI 53c895a_ controller which is not supported by Solaris. However, we can create iSCSI devices in Dom0 and supply them to virtual machines. The following guide is created for Debian 7 which uses _iSCSI Enterprise Target_. Recent Linux kernels replaced it with _LIO_ stack.

 * Install IET packages:
```
# aptitude install iscsitarget iscsitarget-dkms
```
 * Create logical disks for virtual machines. They would be LVM volumes `/dev/mapper/vgmain-sol11--base--lab` and `/dev/mapper/vgmain-centos7--base--lab` in our example.
 * Create targets in `/etc/iet/ietd.conf` file by adding following lines:
```
Target iqn.2154-04.tdc.r520:storage.lab5-sol11-base
    Lun 0 Path=/dev/mapper/vgmain-sol11--base--lab,Type=blockio

Target iqn.2154-04.tdc.r520:storage.lab5-centos7-base
    Lun 0 Path=/dev/mapper/vgmain-centos7--base--lab,Type=blockio
```
Note that target names should match DNS name of a host which provides them.
 * Configure `/etc/iet/initiators.allow` file to forbid Solaris access to disk allocated for CentOS machine and vice versa. Delete or comment out `ALL ALL` line and add lines with target names and IP addresses of corresponding machines:
```
iqn.2154-04.tdc.r520:storage.lab5-sol11-base    192.168.50.179
iqn.2154-04.tdc.r520:storage.lab5-centos7-base  192.168.50.171
```
 * Restart IET daemon:
```
# /etc/init.d/iscsitarget restart
```
 * Configure Solaris initiator. `192.168.50.116` is an IP address of our Dom0 system which provides iSCSI targets.
```
# iscsiadm add discovery-address 192.168.50.116
# iscsiadm modify discovery -t enable
# svcadm restart svc:/network/iscsi/initiator:default
```
 * Similarly configure CentOS initiator:
```
# yum install iscsi-initiator-utils
# systemctl enable iscsid
# systemctl start iscsid
# iscsiadm -m discovery -t sendtargets -p 192.168.50.116
# iscsiadm -m node --login
```
