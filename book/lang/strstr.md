### Strings 

Strings in dynamic tracing languages are wrappers around C-style null-terminated `char*` string, but they behave differently. In SystemTap it is simple alias, while DTrace add extra limitations, for example, you can't access single character to a string. String operations are listed in following table:

---
__Operation__ | __DTrace__ | __SystemTap__
Get kernel string |1,2 `stringof ( expr )` or \
                       `(string) expr` | `kernel_string*()`
Convert a scalar type to a string | `sprint()` and `sprintf()`
Get userspace string | `copyinstr()` | `user_string*()`
Compare strings |2,1 `==`, `!=`, `>`, `>=`, `<`, `<=` -- semantically equivalent to `strcmp`
Concatenate two strings | `strjoin(str1, str2)` | `str1 . str2`
Get string length |2,1 `strlen(str)`
Check if substring is in string | `strstr(haystack, needle)` | `isinstr(haystack, needle)`
---

Note that this operations may be used in DTrace predicates, for example:
```
syscall::write:entry
/strstr(execname, "sh") != 0/ 
{}
```

#### References

* ![image:dtraceicon](icons/dtrace.png) [Strings](http://docs.oracle.com/cd/E19253-01/817-6223/chp-strings/index.html)
* ![image:dtraceicon](icons/dtrace.png) [Actions and Subroutines](http://docs.oracle.com/cd/E19253-01/817-6223/chp-actsub/index.html)
* ![image:staplang](icons/staplang.png) [Strings](https://sourceware.org/systemtap/langref/Language_elements.html#SECTION00062300000000000000)
* ![image:stapset](icons/stapset.png) [A collection of standard string functions](https://sourceware.org/systemtap/tapsets/string.stp.html)

### Structures

Many subsystems in Linux and Solaris have to represent their data as C structures. For example, path to file corresponds from file-related structure `dentry` and filesystem-related structure `vfsmnt`:
```
struct path {
	struct vfsmount *mnt;
	struct dentry *dentry;
};
```

Structure fields are accessed same way it is done in C: in DTrace depending on what you are getting you need to use `->` for pointers and `.` for structures. In SystemTap you should always use `->` which will be contextually converted to `.` where needed. Information about structures is read from CTF sections in Solaris and DWARF sections in Linux, including field names. To get C structure you may need to cast a generic pointer (`void*` in most cases) to a needed structures. In DTrace it is done using C-style syntax:
```
(struct vnode *)((vfs_t *)this->vfsp)->vfs_vnodecovered
```

Conversion in SystemTap is used more often, because in many places, typed pointers are coerced to generic `long` type. It is performed with `@cast` expression which accepts address, name of structure as string (`struct` keyword is optional), and an optional third parameter which contains name of include file, for example:
```
function get_netdev_name:string (addr:long) {
	return kernel_string(@cast(addr, "net_device")->name)
}
```

#### References

* ![image:dtraceicon](icons/dtrace.png) [Structs and Unions](http://docs.oracle.com/cd/E19253-01/817-6223/chp-structs/index.html)
* ![image:staplang](icons/staplang.png) [Expressions](https://sourceware.org/systemtap/langref/Language_elements.html#SECTION000661000000000000000)