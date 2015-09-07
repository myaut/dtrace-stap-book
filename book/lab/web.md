### Web application stack

We will need to setup web stack to complete [exercise 7][app/ex7]. We will use following applications: web server _Apache HTTPD 2.4_, relational database _MySQL Community Edition 5.6_ and PHP interpreter _PHP 5.6_, and content management system _Drupal 7_ on top of them. This guide can be used to setup both CentOS 7 and Solaris 11 except for few commands (they will be marked). We will need to build these programs from source codes to enable USDT probes in them.

!!! DANGER
This guide is intended for lab setup. It could lack security, so do not use it for production systems.
!!!

##### Download programs sources

 * Download sources with `wget`:
```
# wget http://us3.php.net/distributions/php-5.6.10.tar.bz2
# wget http://cdn.mysql.com/Downloads/MySQL-5.6/mysql-5.6.25.tar.gz
# wget http://archive.apache.org/dist/httpd/httpd-2.4.9.tar.gz
# wget http://archive.apache.org/dist/httpd/httpd-2.4.9-deps.tar.gz
```
 * We will also need patch for Apache HTTPD build system:
```
# wget -O dtrace.patch https://bz.apache.org/bugzilla/attachment.cgi?id=31665
```
 * (_Only CentOS7_) Remove programs that were installed from package repositories and install some dependencies:
```
# yum erase php mysql mysql-server httpd
# yum install libxml2-devel bzip2
```
 * (_Only Solaris_) We will have to use GNU Make for all builds, so make an alias to maintain guide uniformity:
```
# alias make=gmake
```
 * Unpack downloaded archives
```
# tar xzvf httpd-2.4.9.tar.gz
# tar xzvf mysql-5.6.25.tar.gz 
# tar xjvf php-5.6.10.tar.bz2 
# tar xzvf httpd-2.4.9-deps.tar.gz
```

##### Build and install MySQL from sources
 
 * Change current directory to one with sources:
```
# cd mysql-5.6.25
```
 * (_Only CentOS7_) Install dependencies:
```
# yum install cmake bison ncurses-devel gcc-c++
```
 * (_Only Solaris_) Install dependencies: 
```
# pkg install pkg:/developer/build/cmake
# pkg install pkg:/developer/parser/bison
```
 * Build and install MySQL (it would be installed into `/usr/local/mysql`)
```
# cmake --enable-dtrace . 
# make -j4 
# make install
```

##### Build and install Apache HTTPD from sources
 
 * Change current directory to one with sources:
```
# cd ../httpd-2.4.9
```
 * (_Only CentOS7_) Install dependencies: 
```
# yum install pcre-devel autoconf flex patch
```
 * (_Only Solaris_) Install dependencies: 
```
# pkg install pkg:/developer/build/autoconf 
# pkg install pkg:/developer/macro/gnu-m4
# pkg install pkg:/developer/lexer/flex
```
 * Apply patch to a build system and recreate configure script:
```
# patch -p0 < ../dtrace.patch
# autoconf
```
 * Create file for building MPM:
```
# (cd server/mpm/event/ && 
    echo "$(pwd)/event.o $(pwd)/fdqueue.o" > libevent.objects)
```
 * Fix `server/Makefile.in` file:
```
# sed -i 's/apache_probes.h/"apache_.*probes.h"/' server/Makefile.in
```
 * Build and install Apache HTTPD (it would be installed into `/usr/local/apache2`):
```
# ./configure --with-included-apr --enable-dtrace
# make -j4 
# make install
```

##### Build and install PHP interpreter from sources
 
 * Change current directory to one with sources:
```
# cd php-5.6.10
```
 * (_Only CentOS7_) Install dependencies: 
```
# yum install libjpeg-turbo-devel libpng12-devel
```
 * (_Only Solaris_) Install dependencies: 
```
# pkg install pkg:/system/library/gcc-45-runtime
```
 * Build and install PHP:
```
# ./configure --enable-debug --enable-dtrace --with-mysql       \ 
    --with-apxs2=/usr/local/apache2/bin/apxs --without-sqlite3  \  
    --without-pdo-sqlite --with-iconv-dir --with-jpeg-dir       \
    --with-gd --with-pdo-mysql
# make -j4
# make install
```

##### Setup MySQL database
 
 * Change directory to a MySQL root directory:
```
# cd /usr/local/mysql
```
 * (_Only CentOS7_) Create mysql user:
```
# groupadd -g 666 mysql
# useradd -u 666 -g mysql -d /usr/local/mysql/home/ -m mysql
```
 * Create data files:
```
# chown -R mysql:mysql data/
# ./scripts/mysql_install_db
```
 * Create `/etc/my.cnf` configuration file:
```
# cat > /etc/my.cnf << EOF
[mysqld]
datadir=/usr/local/mysql/data
socket=/tmp/mysql.sock
user=mysql
# Disabling symbolic-links is recommended to prevent assorted security risks
symbolic-links=0
bind-address=0.0.0.0 

[mysqld_safe]
log-error=/var/log/mysqld.log
pid-file=/var/run/mysqld/mysqld.pid
EOF
```
 * Create log file and directory for PID file:
```
# touch /var/log/mysqld.log && chown mysql:mysql /var/log/mysqld.log
# mkdir /var/run/mysqld/ && chown mysql:mysql /var/run/mysqld/
```
 * Fill system tables:
```
# chown -R mysql:mysql data/
# ./scripts/mysql_install_db --ldata=/usr/local/mysql/data
```
 * Start mysqld daemon:
```
# ./support-files/mysql.server start
```
 * Set MySQL root password to `changeme`:
```
# /usr/local/mysql/bin/mysqladmin -u root password changeme
```
 * Create drupal user in MySQL:
```
# /usr/local/mysql/bin/mysql --user=root -p mysql -h localhost
Enter password: changeme
mysql> CREATE USER 'drupal'@'localhost' IDENTIFIED BY 'password';
mysql> GRANT ALL PRIVILEGES ON * . * TO 'drupal'@'localhost';
mysql> FLUSH PRIVILEGES;
```

##### Setup Apache and PHP interpreter

 * (_Only CentOS7_) Disable firewall:
```
# systemctl disable firewalld
# systemctl stop firewalld
```
 * Change directory to HTTPD root directory:
```
# cd /usr/local/apache2
```
 * Make a backup copy of configuration file and add PHP 5 support to it (you will have to use `gsed` instead of `sed` in Solaris): 
```
# cp conf/httpd.conf conf/httpd.conf.orig
# sed -re 's/^(\s*DirectoryIndex.*)/\1 index.php/' conf/httpd.conf.orig > conf/httpd.conf        
# cat >> conf/httpd.conf <<EOF
# Use for PHP 5.x:
LoadModule php5_module        modules/libphp5.so
AddHandler php5-script  .php
EOF
```
 * Start Apache HTTPD:
```
# ./bin/httpd
```

##### Install Drupal 7 
 
 * Change to a directory with web documents:
```
# cd /usr/local/apache2/htdocs
```
 * Download and unpack Drupal 7:
```
# cd /tmp
# wget http://ftp.drupal.org/files/projects/drupal-7.38.zip
# cd /usr/local/apache2/htdocs/
# unzip /tmp/drupal-7.38.zip
# mv drupal-7.38/ drupal/
# chown -R daemon:daemon .
```
 * Create `drupal` database:
```
# /usr/local/mysql/bin/mysql --user=drupal -p -h localhost 
Enter password: password
mysql> CREATE DATABASE drupal;
```
 * Enter `http://SERVER ADDRESS/drupal/install.php` in web browser and follow Drupal installer instructions. Use following parameters when setting up database:
    * Database name: drupal
    * Database username: drupal
    * Database password: password

##### Install Drupal module devel and setup test data

 * Download and install it:
```
# wget -O /tmp/devel-7.x-1.5.tar.gz http://ftp.drupal.org/files/projects/devel-7.x-1.5.tar.gz
# cd /usr/local/apache2/htdocs/drupal/modules 
# tar xzvf /tmp/devel-7.x-1.5.tar.gz
```
 * Access index page of Drupal, choose _Modules_ in top-level menu, and check _Devel_ and _Devel generate_ in the shown list, then click on _Save Configuration_.
 * After enabling modules, choose _Configure_ for _Devel generate_ module, and choose _Generate content_ in a menu, pick option _Article_ and click _Generate_. 50 test pages should appear at index page.
 
!!! NOTE
To start services, use following commands:
```
# /usr/local/mysql/support-files/mysql.server start
# /usr/local/apache2/bin/httpd
```
!!!

 
