from tsdoc.blocks import *

import re
import os
import string 

class _Frame(object):
    def __init__(self, cls, idx, tail=None, **options):
        self.idx = idx
        self.cls = cls
        self.tail = tail
        
        self.text = []                   # Array of text chunks
        self.options = options

class MarkdownParseError(Exception):
    def __init__(self, idx, message, stack):
        self.idx = idx
        self.message = message
        self.stack = stack
    
    def __str__(self):
        lines = ['error at {0}: {1}, parser stack:'.format(self.idx, self.message)]
        for frame in self.stack:
            optstr = ', '.join('{0}={1}'.format(k, v) 
                               for k,v in frame.options.items())
            lines.append(
                '\t[{0:4}] {1}({2}, {3}) -> {4}'.format(
                    frame.idx, frame.cls.__name__, len(frame.text), optstr, repr(frame.tail)))
        
        return '\n'.join(lines)

class MarkdownParser(object):
    TRACE = (os.environ.get('MDTRACE') == '1')
    LAST_TRACED_IDX = -1
    
    class _ctlcount(object):
        # Checks that count of control characters matches expected value
        def __init__(self, expected):
            self.expected = expected
        def __call__(self, f):
            def wrapper(parser, idx, count):
                if count != self.expected:
                    return idx
                return f(parser, idx, count)
            wrapper.__name__ = f.__name__
            return wrapper
    
    class _block(object):
        # Checks that only whitespace characters are between previous newline or
        # (for unordered lists -- replaces count with number of whitespace characters)
        def __init__(self, ul=False):
            self.ul = ul
            
        def __call__(self, f):
            def wrapper(parser, idx, count):
                # Look back previous newline
                try:
                    nlidx = parser.text.rindex('\n', 0, idx)
                except ValueError:
                    nlidx = 0
                    
                ws = parser.text[nlidx:idx]
                if not all(c in string.whitespace 
                           for c in ws):
                    return idx
                
                if self.ul:
                    count = len(ws)
                
                return f(parser, idx, count)
            wrapper.__name__ = f.__name__
            return wrapper
        
    class _ignore(object):
        # Ignores certain certain tags when in context of certain parts/blocks
        def __init__(self, *classes):
            self.classes = classes
        def __call__(self, f):
            def wrapper(parser, idx, count):
                top = parser.stack[-1]
                if top.cls in self.classes:
                    return idx
                return f(parser, idx, count)
            wrapper.__name__ = f.__name__
            return wrapper
    
    class _seek_char(object):
        # Seeks for tail char and advance idx correspondingly while passing 
        # text before it as third f() argument
        def __init__(self, endchar):
            self.endchar = endchar
        def __call__(self, f):
            def wrapper(parser, idx, count):
                bidx = idx + count
                try:
                    cidx = parser.text.find(self.endchar, bidx)
                except ValueError:    
                    return idx
                
                # Actual tag's length is larger because it contains tag's extra data
                count = (cidx - idx + len(self.endchar))
                
                return f(parser, idx, count, parser.text[bidx:cidx])
            wrapper.__name__ = f.__name__
            return wrapper
    
    def __init__(self, text, name=''): 
        self.name = name
        self.text = text
        
        self.blocks = []
        self.stack = [_Frame(Paragraph, 0)]
    
    def _trace1(self, idx, idx2):
        if self.TRACE and self.LAST_TRACED_IDX != idx:
            top = self.stack[-1]
            nearby = repr(self.text[idx-4:idx+4])
            
            print '{0:4}->{1:<4} {2:14} {3} {4} {5}'.format(idx, idx2, nearby, 
                    top.cls.__name__, repr(top.tail), top.options)
            self.LAST_TRACED_IDX = idx
    
    def _trace2(self, fmtstr, *args, **kwargs):
        if self.TRACE:
            print '\t' + fmtstr.format(*args, **kwargs)
        
    def _count(self, charcls, idx):
        count = 0
        
        while idx < len(self.text):
            char = self.text[idx]
            idx += 1
            
            # Hack for end paragraph -- allow for empty strings
            if charcls[0] == '\n' and char in ' \t':
                continue

            if char not in charcls:
                break
            
            count += 1
            
        return count 
    
    def _call_handlers(self, table, idx, top):
        for cls, func in table:
            if issubclass(top.cls, cls):
                self._trace2('SUBCALL ({0}->{1}) {2}', top.cls.__name__, cls.__name__, func.__name__)
                func(self, idx, top)
    
    def _push(self, idx, frame):
        top = self.stack[-1]
        
        if not issubclass(top.cls, Block):
            # Reject frame if current top-level frame in non-block
            self._trace2('REJ  {0} ({1})', frame.cls.__name__, top.cls.__name__)
            return
        
        self._trace2('PUSH {0} {1} {2}', frame.cls.__name__, repr(frame.tail), frame.options)
        
        if top.idx != idx:
            top.text.append(self.text[top.idx:idx])
            top.idx = idx
        
        self.stack.append(frame)

    def _pop(self, idx, eidx, frame=None):
        top = self.stack.pop()
        if idx != top.idx:
            top.text.append(self.text[top.idx:idx])
        
        self._trace2('POP {0:x} {1} {2} {3}', id(top), top.cls.__name__, len(self.stack), len(self.blocks))
        
        try:
            self._call_handlers(self.PRE_POP_TABLE, idx, top)
        except StopIteration:
            self.stack.append(top)      # We are not ready yet
            return
        
        if issubclass(top.cls, Block):
            top.options['parts'] = top.text
            part = top.cls(**top.options)
            toplevel = (len(self.stack) == 1 and not self.stack[0].text)
        else:
            part = top.cls(''.join(top.text), **top.options)
            toplevel = False
        
        if not self.stack or toplevel:
            # Top-level block -- add it to global list of blocks
            self.blocks.append(part)
            self.stack = [_Frame(Paragraph, eidx)]
            return
        
        newtop = self.stack[-1]
        newtop.text.append(part)
        newtop.idx = eidx
        
        if frame and top is not frame:
            self._trace2('UNWIND {0:x} {1}', id(frame), frame.cls.__name__)
            self._pop(idx, eidx, frame)
            return
        
        self._call_handlers(self.POST_POP_TABLE, idx, newtop)
    
    def _check_tail(self, idx):
        for frame in reversed(self.stack):
            if not frame.tail:
                continue
            
            tidx = idx + len(frame.tail)
            
            if self.text[idx:tidx] == frame.tail:
                # Recursively pop elements unless frame is popped out of stack    
                self._trace1(idx, tidx)
                self._trace2('TAILCHK {0:x} {1} {2}', id(frame), frame.cls.__name__, repr(frame.tail))
                self._pop(idx, tidx, frame)
                return tidx
        
        return idx
        
    def parse(self):
        idx = 0
        length = len(self.text)
        
        while idx < length:
            char = self.text[idx]
            
            tidx = self._check_tail(idx)
            if tidx != idx:
                idx = tidx
                continue
            
            for charcls, func in self.CHAR_TABLE:
                if char in charcls:
                    count = self._count(charcls, idx) # Forward-look count of the "control characters"
                    
                    self._trace1(idx, idx + count)
                    self._trace2('CALL {0} {1:4} {2:16}', count, repr(char), func.__name__)
                    
                    nidx = func(self, idx, count)
                    
                    if nidx > idx:     # if index was advanced, sequence was successfully parsed
                        idx = nidx
                        break
            else:
                idx += 1
        
        self._pop(length, length, self.stack[0])   # unwind stack
        
        return self.blocks
    
    # -------------------------------
    # Tag parsers -- they are chosen from CHAR_TABLE table and being called for each matched character
    
    @_ignore(Code)
    def _escape(self, idx, count):
        # Create a new chunk of text on the escape symbol
        top = self.stack[-1]
        
        top.text.append(self.text[top.idx:idx])
        top.idx = idx + 1
        
        return idx + 2
    
    def _end_paragraph(self, idx, count):
        if count == 1:
            return 
        
        self._trace1(idx, idx + count)
        
        # Find top-level block. If it is a paragraph, pop it and re-create
        for frame in reversed(self.stack):
            self._trace2('ENDPARA {0:x} {1} {2}', id(frame), frame.cls.__name__, 
                                                  issubclass(frame.cls, Paragraph))
            
            if issubclass(frame.cls, Incut) or issubclass(frame.cls, Code):
                # Ignore \n\n s in incuts and code-blocks
                break
                
            if issubclass(frame.cls, Paragraph):
                self._pop(idx, idx, frame)
                self._push(idx, _Frame(Paragraph, idx + count))
                return idx + count
        
        return idx
     
    @_ctlcount(3)
    @_ignore(Code)
    def _breakline(self, idx, count):
        self._push(idx, _Frame(BreakLine, idx + count))
        self._pop(idx + count, idx + count)
        return idx + count
    
    @_block()
    @_ignore(Code)
    def _header(self, idx, count):
        self._push(idx, _Frame(Header, idx + count, size=count))
        return idx + count
    
    @_block()
    @_ctlcount(1)
    @_ignore(Code)
    def _blockquote(self, idx, count):
        self._push(idx, _Frame(BlockQuote, idx + count))
        return idx + count
    
    @_block(ul=True)
    @_ignore(Code)
    def _list_entry(self, idx, count):
        ul = None
        for frame in self.stack:
            if frame.cls is ListBlock and frame.options['indent'] == count:
                ul = frame
                break
        
        if ul is None:
            ul = _Frame(ListBlock, idx, indent=count)
            self._push(idx, ul)
        else:
            while self.stack[-1] is not ul:
                self._pop(idx, idx)
        
        self._push(idx, _Frame(ListEntry, idx + 1, level=count))
        return idx + 1
    
    @_ignore(Code, InlineCode, Link)
    def _styled(self, idx, count):
        if self.text[idx-1] not in string.whitespace + string.punctuation:
            return idx
        
        tag = self.text[idx:idx+count]
        rtag = ''.join(reversed(tag))
        
        if count == 1:
            cls = ItalicText
        elif count == 2:
            if tag == '_*':
                cls = BoldItalicText
            else:
                cls = BoldText
        else:
            return idx
        
        self._push(idx, _Frame(cls, idx+count, rtag))
        return idx + count
    
    @_ctlcount(3)
    @_ignore(Code, InlineCode, Link)
    @_seek_char(' ')
    def _span(self, idx, count, options):
        self._push(idx, _Frame(Span, idx+count, '___',
                               style=options))
        return idx + count
    
    @_ctlcount(1)
    @_ignore(Code, InlineCode)
    def _inline_code(self, idx, count):
        self._push(idx, _Frame(InlineCode, idx+1, '`'))
        return idx + count
    
    @_block()
    @_ctlcount(3)
    @_seek_char('\n')
    def _code_block(self, idx, count, options):
        self._push(idx, _Frame(Code, idx + count, '```'))
        return idx + count
    
    @_block()
    @_ctlcount(5)
    @_seek_char('\n')
    def _listing(self, idx, count, options):
        fname = options.strip()
        frame = _Frame(CodeListing, idx + count, fname=fname)
        
        with open(fname) as f:
            frame.text.append(f.read())
        
        self._push(idx, frame)
        self._pop(idx + count, idx + count)
        return idx + count
    
    @_ctlcount(4)
    def _breakpoint(self, idx, count):
        raise MarkdownParseError(idx, 'breakpoint', self.stack)
    
    @_block()
    @_ignore(Code)
    @_ctlcount(3)
    @_seek_char('\n')
    def _incut(self, idx, count, options):
        style = options.strip()
        if not style:
            raise MarkdownParseError(idx, 'incut has empty style', self.stack)
        
        self._push(idx, _Frame(Incut, idx + count, '!!!',
                               style=options.strip()))
        self._push(idx, _Frame(Paragraph, idx + count))
        
        return idx + count
    
    @_ignore(Code, InlineCode)
    def _link(self, idx, count):
        chars = self.text[idx:idx+count]
        
        if chars == '![':
            cls = Image
        elif chars == '[':
            cls = Link
        else:
            return idx
        
        self._push(idx, _Frame(cls, idx + count, ']',
                               type=Link.INVALID))
        return idx + count
    
    @_ignore(Code, InlineCode)
    @_ctlcount(3)
    @_seek_char('\n')
    def _table(self, idx, count, options):
        self._push(idx, _Frame(Table, idx + count, tail='---'))
        self._post_pop_row(idx + count, None)
        
        return idx + count
    
    CHAR_TABLE = [
        ('$$$$', _breakpoint),
        ('\\', _escape),
        ('\n\n', _end_paragraph),
        
        ('>>>', _breakline),
        ('>', _blockquote),
        ('#', _header),
        ('*', _list_entry),
        ('___', _span),
        ('_*', _styled),
        ('`', _inline_code),
        ('```', _code_block),
        ('`````', _listing),
        ('!!!', _incut),
        ('![', _link),
        
        ('---', _table)
        ]
    
    # -------------------------------
    # Block pre- and post-processing. Before removing block from stack they pre-process some data in it depending
    # on block class
    
    def _post_list(self, idx, top):
        del top.options['indent']
    
    def _post_code(self, idx, top):
        # TODO: implement syntax hightlighting here
        
        top.text = [text.strip()
                    for text in top.text]
        
    def _post_link(self, idx, top):
        char = self.text[idx + 1] if idx < (len(self.text) - 1) else ''
        
        if char == '[':
            top.options['type'] = Link.INTERNAL
            self._post_link_2(idx, top)
        elif char == '(':
            top.tail = ')'
            top.options['type'] = Link.EXTERNAL
            self._post_link_2(idx, top)
        elif top.options['type'] == Link.INVALID:
            top.cls = Reference
            top.options = {}
        else:
            top.options['where'] = ''.join(top.text)
            top.text = top.options['text']
            del top.options['text']
    
    def _post_link_2(self, idx, top):
        top.idx = idx + 2
        
        # Save link's text, because actual top.text will contain link itself
        top.options['text'] = top.text
        top.text = []
        
        raise StopIteration()
    
    PRE_POP_TABLE = [
        (ListBlock, _post_list),
        (Code, _post_code),
        (Link, _post_link)
        ]
    
    def _post_pop_row(self, idx, top):
        self._push(idx, _Frame(TableRow, idx, tail='\n'))
        self._post_pop_cell(idx, None)
    
    def _post_pop_cell(self, idx, top):
        # Parse cell's rowspan, colspan
        char = self.text[idx]
        if char == '|':
            idx += 1
        if char == '\n':
            idx += 1
        
        regex = re.compile('(\d+),(\d+)')
        m = regex.match(self.text, idx)
        if m:
            self._push(idx, _Frame(TableCell, m.end(), tail='|',
                                   colspan=int(m.group(1)),
                                   rowspan=int(m.group(2))))
            return
        
        self._push(idx, _Frame(TableCell, idx, tail='|'))
    
    POST_POP_TABLE = [
        (Table, _post_pop_row),
        (TableRow, _post_pop_cell)
        ]
    
if __name__ == "__main__":
    import sys
    
    _ = sys.argv.pop(0)    
    if sys.argv:
        fp = file(sys.argv[0])
        text = fp.read()
        fp.close()
    else:
        text = r"""

# Recommendation
[__docspace__:index]

Use [wikipedia](https://en.wikipedia.org/wiki/Python_\(programming_language\)) or [wiki][wiki/python#python] to get info on **Python**
_Inline_ blocks are also good. Such as ` \`code\` ` or ` _code_ `

Some __lorem_ipsum__ stuff here.  >>>
This is \_escaped thing. Escaping: \\
[Tag] Ouch!

### List

* FIRST
  * *A*
* SECOND

```
int a = 777 * 5;

void f();
    ```

````` /usr/include/stdio.h
````` /usr/include/stdlib.h

!!! DEF
---
2,1 aaaa
1 | 2
3 | 4
---

Some text

More text
!!!
        """

    parser = MarkdownParser(text)    
    blocks = parser.parse()
    
    print '-----------------'
    
    for block in blocks:
        pprint_block(block)