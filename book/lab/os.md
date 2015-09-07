### Setting up Operating Systems

Originally we used Virtual Machines for Oracle VirtualBox with Solaris 11.0 and CentOS 6.4. Unfortunately, these versions become stale, while VirtualBox is a second-level hypervisor which complicates performance analysis experiments. 

Actual version of this book was modified to support Solaris 11.2 and CentOS 7.0. They were installed in a Xen 4.4 environment in HVM machines. I assume that you were installed these operating systems and already performed basic setup like setting IP address or root password. 

#### Setting up CentOS 7

 * You will need debuginfo packages to access debug information. They are located in separate CentOS repository which you will need to turn on:
```
# sed -i 's/^enabled=0/enabled=1/g' /etc/yum.repos.d/CentOS-Debuginfo.repo
```

!!! WARN
CentOS 7.0 contains incorrect GPG key for debuginfo repository like described in [bug 7516](https://bugs.centos.org/view.php?id=7516), so you will also need to update `centos-release` package:
```
# yum install centos-release
```
!!!

 * Install SystemTap
```
# yum install systemtap systemtap-sdt-devel systemtap-client
```
 * Run `stap-prep` script. That script will install packages that are needed for building kernel modules and debuginfo packages:
```
# stap-prep
```

!!! NOTE
`kernel-debuginfo` may be installed manually using YUM package manager. In that case, however, you should add precise version of kernel to a package name. Otherwise YUM will install newest version that probably wouldn't match kernel you running. 
!!!

 * Install `debuginfo-install` utility:
```
# yum install yum-utils
```
 * Install debug information for userspace programs:
```
# debuginfo-install cat python
```
 * Change `/tmp` mount point to tmpfs. To do that, add following line to `/etc/fstab` file:
```
tmpfs        /tmp       tmpfs     defaults          0 0
```
   After that clean up /tmp and run `mount -a` command.
 * Building TSLoad workload generator and its modules
   * Install SCons
```
# yum install wget
# cd /tmp
# wget 'http://prdownloads.sourceforge.net/scons/scons-2.3.4-1.noarch.rpm'
# rpm -i scons-2.3.4-1.noarch.rpm
```
   * Install development files:
```
# yum install libuuid-devel libcurl-devel
```
   * Build a workload generator:
```
# git clone https://github.com/myaut/tsload
# cd tsload/agent
# scons --prefix=/opt/tsload install
```
   * Build loadable modules:
```
# git clone https://bitbucket.org/sergey_klyaus/dtrace-stap-book.git
# cd dtrace-stap-book/tsload
# scons --with-tsload=/opt/tsload/share/tsload/devel install
```
 *  Install OpenJDK7:
```
# yum install java-1.7.0-openjdk-devel.x86_64
```

#### Setting up Solaris 11.2

 * Building TSLoad workload generator and its modules
   * Install SCons
```
# wget 'http://prdownloads.sourceforge.net/scons/scons-2.3.4.tar.gz'
# tar xzvf scons-2.3.4.tar.gz
# cd scons-2.3.4/
# python setup.py install
```
   * Install development files:
```
# pkg install pkg:/developer/gcc-45
# pkg install pkg:/developer/build/onbld
```
   * Build a workload generator:
```
# git clone https://github.com/myaut/tsload
# cd tsload/agent
# scons --prefix=/opt/tsload install
```
   * Build loadable modules:
```
# git clone https://bitbucket.org/sergey_klyaus/dtrace-stap-book.git
# cd dtrace-stap-book/tsload
# scons --with-tsload=/opt/tsload/share/tsload/devel install
```
 * Install JDK7:
```
# pkg install --accept pkg:/developer/java/jdk-7
```
