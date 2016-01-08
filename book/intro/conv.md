### Typographic conventions

This is a book published on the web and so it doesn't have any "typography", but certain parts of text are decorated with certain styles, thus we describe them in this section of the book.

---
_Meaning_ | _Example_
First appearance of new terms | _Central processing unit_ (_CPU_) executes program code.
Multiple terms linked with each other | CPU consists of __execution units__, __cache__ and __memory controller__.
Definition of a term |  \
  !!! DEF 
  According to this book,
  > A _central processing unit_ (_CPU_) executes program code.
  !!! 
Additional information about OS or hardware internals | \
  !!! INFO
  Do not read me if you already know me the answer
  !!!
Notes and some additional information                 | \
  !!! NOTE
  I am note and I am providing external information about the implementation
  !!! \
  !!! WARN
  I will warn you about some implementation quirks
  !!!
Information that some of the examples or code in the section is not suitable for production use | \
  !!! DANGER
  Never try to do `rm -rf /` on your home computer.
  !!!
Function name, or name of the probe, any other entity that exist in source code | \
  If you want to print a line on standard output in pure C, use `puts()`
Chunk of the code that has to be used or command to be executed | \
  ```
int main() {
    puts("Hello, world");
}                             
  ``` \
  ```
$ perl -se '                     
    print "Hello, $who" . "\n"
    ' -- -who=world
  ``` 
Placeholders in program examples are covered in _italic_ | \
  ```
  puts(<i>output-string</i>)
  ```
Large portions of example outputs may have some output outlined with bold: | \
  ```
$ gcc hello.c -o hello
$ ./hello
<b>Hello, world</b>
  ```
Large program listing (if you want to show it, press on "+" button) | \
  ````` scripts/src/hellouser.py 
---

#### Structural diagrams

Many kernel-related topics will contain structural diagrams which will represent kernel data structures like this:

![image](solaris/streams.png)

In this example two instances of `mblk_t` structure (which is typedef alias) are shown which are linked together through pair of `mblk_t` pointers `b_next` and `b_prev`. Not all fields are shown on this diagram, types are omitted, while order of fields may not match real one. Following conventions are used in this type of diagrams:

---
_Example code_ | _Diagram and explanation_
 ```
struct structB {
    int field10;
    char field20;
};
struct structA {
    struct structB* bp;
    int field1;
};
 ``` | ![ab](conv/pointer.png) >>> \
       structure `structA` points to instance of `structB`
 ```
struct structA;
struct structB {
    int field10;
    struct structA* ap;
};
struct structA {
    struct structB* bp;
    int field1;
};
 ``` | ![ab](conv/reverse.png) >>> \
       structure `structB` contains backward pointer to structure `structA`
 ```
struct structA {
    struct structB* bp;
    int field1;
    struct {
        char c1;
        char c2;
    } cobj;
};
 ``` | ![ab](conv/embed.png) >>> \
       structure `structA` has embedded structure (not neccessarily to be anonymous)
 ```
struct structB {
    int field10;
    char field20;
};
struct structA {
    struct structB* bp;
    int field1;
};
 ``` | ![ab](conv/array.png) >>> \
       structure `structA` points to a dynamic array of structures `structB`
 ```
struct structB {
    int field10;
    char field20;
    struct list_head node;
};
struct structA {
    struct list_head blist;
    int field1;
};
 ``` | ![ab](conv/list.png) >>> \
       structure `structA` contains head of linked list of `structB` instances >>> \
       Various structure relations can be shown with this type of arrows:      \
         * Single solid glyph shows node-to-node relations in linked list      \
         * Double solid glyphs shows head-to-node relations in linked list      \
         * Double dashed glyphs shows various tree-like relations like RB tree in Linux
---

#### Timeline diagrams

Timeline diagrams are used to show various processes that exist in traced system and chain of events or operations happening with them and at the same time contains names of probes:

![image:timeline](timeline.png)

This diagram should be read like this:

    * Thick ___##6666ff **colored** ___ arrows represent flow of some processes -- usually they are threads or processes in a system. ___##999999 **Gray** ___ arrows represent processes that are inactive for some reason (usually, blocked and thus cannot be executed on CPU). Arrows corresponding to the same process share same baseline. 
    * Thin black arrows demonstrate transfer of control between several operations. In this example `puts()` call triggers `write` system call. Some of them may be omitted.
    * Thin ___##ff6600 colored___ lines demonstrate subsequent chain of events unrelated to the process. In this example phrase `Hi, Frank` arrives in Konsole window (graphic terminal).
    * Text in dashed rectangles contains name of ___##003380 SystemTap___ and ___##800000 DTrace___ probes corresponding to the operations or events happening with the process.

Virtual time axis beginning at the top and it is vertical.

!!! DANGER
Probes shown in this example are purely fictional.
!!!