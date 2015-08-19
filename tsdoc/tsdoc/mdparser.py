import os
import string
import traceback

from tsdoc.blocks import *

class MarkdownParser:
    TRACE = False
    _TRACE_FILES = []
    
    class ParseException(Exception):
        def __init__(self, idx, lineno, msg):
            Exception.__init__(self,
                               "Parsing exception '%s' at line %d (idx: %d)" % (msg, lineno, idx))
    
    
    def __init__(self, text, name=''):                
        self._escape = []
        
        self.text_pos = 0
        self.newline_pos = 0
        self.block_nl_pos = -1
        
        self.default_state = {}
        self.list_levels = {}
        
        self.init_state(
            escape_pos = -1,
            
            link_pos = -1,
            link_image = False,
            link_text_end = -1,
            link_type = -1,
            link_end_char = '',
            
            block_quote = False,
            
            header_size = -1,
            
            list_level = -1,
            
            in_code = False,
            
            bold_char = '',
            italic_char = '',
            
            icode_cnt = -1)
        
        self.name = name
        self.lineno = 1
        
        if name in self._TRACE_FILES:
            self.TRACE = True
        
        self.block = Paragraph()
        self.list_blocks = {}
        self.list_parent = None
        self.blocks = []
        
        self.table_parent = None
        self.table_block = None
        self.table_row = None
        
        self.incut = None
        
        self.text = text
    
    def init_state(self, **state):
        for (attr, value) in state.items():
            self.default_state[attr] = value
            setattr(self, attr, value)
    
    def _error(self, idx, e):
        traceback.print_exc()
        lineno = self.text[:idx].count('\n')
        print 'Parsing error at %s:%d:%d -> %s' % (self.name, lineno, idx, str(e))
    
    def parse(self):
        idx = 0
        length = len(self.text)
        
        # Indexes that contain escape positions
        escape = []
        
        while idx < length:
            char = self.text[idx]
            
            if self.TRACE:
                self.dump_state(idx)
            
            if char == '`':
                try:
                    idx = self._parse_code(idx, char)
                except Exception as e:
                    self._error(idx, e)
                continue
            
            if char == '-':
                try:
                    idx = self._parse_table(idx, char)
                except Exception as e:
                    self._error(idx, e)
                continue
            
            if char == '!':
                try:
                    idx = self._parse_incut(idx, char)
                except Exception as e:
                    self._error(idx, e)
                continue
            
            if char == '>':
                count = self.ctl_count(idx, '>')
                
                if count == 1:
                    match, prefix = self.prefix(self.newline_pos, idx - 1, ' \t')
                    if match:
                        self.block = BlockQuote()
                        idx += 1
                        self.text_pos += 1
                        continue
                elif count == 3:
                    self.end_text(idx)
                    self.block.add(BreakLine())
                    self.begin_text(idx, count)
                    idx += count
                    continue
            
            if self.in_code:
                idx += 1
                continue
            
            if char == '\n':
                self.newline(idx)
            elif char == '\\':
                self.escape(idx)
            else:
                if self.escape_pos > 0:
                    # Do not parse anything if symbol was escaped
                    # symbol or we're inside code block
                    self.escape_pos = -1
                    idx += 1
                    continue
                
                try:
                    idx = self._parse_at(idx, char)
                except Exception as e:
                    self._error(idx, e)
                
                continue
                
            idx += 1
        
        self.end_block(idx)
                                    
        return self.blocks
    
    def _parse_code(self, idx, char):
        count = self.ctl_count(idx, '`')
        
        if count >= 5:
            return self.code_listing_block(count, idx)
        
        if count >= 3:
            # this is code block and not inline code
            if self.icode_cnt == -1:
                self.code_block(count, idx)
        elif not isinstance(self.block, Code):
            # inline code
            self.inline_code(count, idx)
        
        return idx + count
    
    def _parse_incut(self, idx, char):
        count = self.ctl_count(idx, '!')
             
        if count == 3:
            # have to parse incut style
            incut = None
            if not self.incut:
                nlidx = self.text.find('\n', idx + count)
                incut = self.text[idx+count+1:nlidx]
                incut = incut.split()
                
                count = nlidx - idx
                
            
            self.incut_block(count, idx, incut)
        
        return idx + count
    
    def _parse_table_cell(self, idx):
        count = 0
        while self.text[idx + count] not in string.whitespace:
            count += 1
            
        try:
            span = self.text[idx:idx+count]
            colspan, rowspan = map(int, span.split(','))
            self.block = TableCell(colspan, rowspan)
            
            self.text_pos += count
        except Exception as e:
            self.block = TableCell()
        
        self.table_row.add(self.block)
        
        return idx + count
    
    def _parse_table(self, idx, char):
        count = self.ctl_count(idx, '-')
        match, _ = self.prefix(self.newline_pos, idx - 1, ' \t')
        
        if count >= 3 and match:
            if self.table_block is None:
                self.table_block = Table()
                self.block.add(self.table_block)
                self.table_parent = self.block
            else:
                self.table_row = None
                self.table_block = None
                self.block = self.table_parent
                
            self.text_pos += count
            
        return idx + count
    
    def _parse_at(self, idx, char):
        if self.table_row is not None and char == '|':
            self.end_block(idx, False)
            return self._parse_table_cell(idx + 1)
        elif char == '#':
            if self.ctl_count(idx, char) > 1:
                return idx + 1
            
            match, prefix = self.prefix(self.newline_pos, idx, '#')
            if match:
                self.begin_text(idx - len(prefix) + 1, len(prefix) + 1,
                                header_size = len(prefix))
        elif char == '*':
            match, prefix = self.prefix(self.newline_pos, idx - 1, ' \t')
            if match:
                self.list_entry(idx, prefix)
            else: 
                count = self.ctl_count(idx, '*')
                self.styled_text(count, idx, char)
                return idx + count 
        elif char == '`':
            count = self.ctl_count(idx, '`')
            self.inline_code(count, idx)
            return idx + count
        elif char == '_':
            count = self.ctl_count(idx, '_')
            self.styled_text(count, idx, char)
            return idx + count
        elif char == '[':
            if self.link_pos == -1:
                self.link_image = self.text[idx - 1] == '!'
                self.begin_text(idx - 1 if self.link_image else idx, 
                                2 if self.link_image else 1, 
                                link_pos = idx)
        elif char in [']', ')']:
            if not self.link_end_char and char == ']':
                char = self.text[idx + 1]
                
                if char == '[':
                    self.link_type = Link.INTERNAL
                    self.link_end_char = ']'
                    self.link_text_end = idx
                    return idx + 1
                elif char == '(':
                    self.link_type = Link.EXTERNAL
                    self.link_end_char = ')'
                    self.link_text_end = idx
                    return idx + 2
                else:
                    # Just a tag
                    self.end_text(idx, 1, Reference,
                                  link_pos = -1,
                                  link_image = False)
            elif self.link_end_char == char:
                where = self.text[self.link_text_end + 2:idx]
                
                self.end_text(self.link_text_end, 
                              idx - self.link_text_end + 1, 
                              Image if self.link_image else Link, 
                              [self.link_type, where],
                              link_pos = -1,
                              link_text_end = -1,
                              link_end_char = '',
                              link_type = -1,
                              link_image = False)
        
        return idx + 1
       
    def prefix(self, start, idx, chars):
        prefix = self.text[start:idx+1]
        match = all(c in chars for c in prefix)
        
        if self.TRACE:
            print '\t prefix:', match, repr(prefix)
        
        return match, prefix
    
    def ctl_count(self, idx, char):
        # Some of Markdown control symbols may be duplicated
        length = len(self.text)
        count = 0
        
        while idx < length and self.text[idx] == char:
            count += 1
            idx += 1
        
        if self.TRACE:
            print '\t ctl: ', count, repr(self.text[idx-count:idx])
            
        return count
    
    def list_entry(self, idx, prefix):
        self.end_text(idx)
        
        level = self.get_list_level(prefix)
        list_levels = self.list_blocks.keys()
        
        if level in self.list_blocks:
            list_block = self.list_blocks[level]
        else:
            list_block = ListBlock()
            self.list_blocks[level] = list_block
            
            parent_level = level - 1
            while parent_level >= 0:
                try:
                    self.list_blocks[parent_level].add(list_block)
                    break
                except:
                    parent_level -= 1
            else:
                pass
            
            if self.list_parent is None:
                self.list_parent = self.block
                self.list_parent.add(list_block)
        
        for olevel in list_levels[:]:
            if olevel > level:
                del self.list_blocks[olevel]
        
        self.block = ListEntry(level)
        list_block.add(self.block)
        
        if self.TRACE:
            print '\t list_entry: level: %d blocks: %s cur: %s' % (
                            level, self.list_blocks, list_block)
            pprint_block(self.list_parent)
    
    def get_list_level(self, prefix):
        indent = len(prefix)
                        
        if indent in self.list_levels:
            level = self.list_levels[indent]
        else:
            level = 1
            for indent2 in sorted(self.list_levels.keys()):
                if indent < indent2:
                    level = self.list_levels[indent2] - 1
                    break
            else:
                if self.list_levels:
                    level = max(self.list_levels.values()) + 1
            
            self.list_levels[indent] = level
        
        if self.TRACE:
            print '\t list_level:', indent, self.list_levels
        
        return level
    
    def escape(self, idx):
        if self.escape_pos == -1:
            self._escape.append(idx)
            self.escape_pos = idx
        else:
            self.escape_pos = -1
    
    def newline(self, idx):
        if self.table_block is not None:
            if idx - 1 not in self._escape:
                # End current cell
                self.end_block(idx, False)
                
                self.table_row = TableRow()
                self.table_block.add(self.table_row)
                
                self._parse_table_cell(idx + 1)
        
        if self.header_size >= 0:
            self.end_text(idx, 1, Header, [self.header_size], 
                          header_size=-1)
        
        if self.block_nl_pos >= 0:
            match, prefix = self.prefix(self.block_nl_pos, idx, '\n ')
            if match and prefix.count('\n') >= 2:
                # Two or more consequent newlines - block ended
                self.end_block(idx)
                self.block_nl_pos = -1
            else:
                self.block_nl_pos = idx
        else:
            self.block_nl_pos = idx
        
        self.newline_pos = idx + 1
    
    def styled_text(self, count, idx, char):
        # FIXME: Way to support 'bold+italic'
        if count == 2:
            self._styled_text_impl(idx, count, BoldText,
                                   bold_char=char)
        else:
            self._styled_text_impl(idx, count, ItalicText,
                                   italic_char=char)
    
    def _styled_text_impl(self, idx, count, klass, **state):
        # Do not interpret _s and *s inside strings
        begin = self.text[idx - 1] in (string.whitespace + string.punctuation) and  \
                    self.link_pos == -1
        
        attr, char = state.items()[0]
        value = getattr(self, attr)
        
        if not value:
            if begin:
                self.begin_text(idx, count)
                setattr(self, attr, char)
        elif value == char:
            self.end_text(idx, count, klass)
            setattr(self, attr, '')
    
    def inline_code(self, count, idx):
        if self.icode_cnt == -1:
            self.begin_text(idx, count, 
                            icode_cnt=count,
                            in_code = True)
        elif self.icode_cnt == count:
            self.end_text(idx, count, InlineCode, 
                          icode_cnt=-1,
                          in_code = False)
    
    def begin_text(self, idx, count, **new_state):
        # End previous chunk of text
        self.end_text(idx, count)
        
        if self.TRACE:
            opttext = 'BEGIN '
            self.dump_state(idx, opttext)
        
        for (attr, value) in new_state.items():
            setattr(self, attr, value) 
            
            if self.TRACE:
                print '\t%s -> %s' % (attr, value)
    
    def end_text(self, idx, count = 1, klass = str, params = [], **new_state):
        '''Generic function to handle text. Adds text from 
        start to idx to current block. By default start is self.TEXT,
        but this may be overriden through field name.
        
        If requested - constructs custom text object (klass + params)
        '''
        # Add prevous text as plain text
        text = self.text[self.text_pos:idx]
        
        if self.TRACE:
            opttext = 'END: %d..%d -> %s(%s)' % (self.text_pos, idx, 
                                              klass.__name__, params)
            self.dump_state(idx, opttext)
        
        if self._escape:
            text = self._filter_escape(text)
            self._escape = []
        
        whitetext = all(char in string.whitespace
                        for char in text)
        if text and not whitetext or klass == Link:
            self.block.add(klass(text, *params))
        
        for (attr, value) in new_state.items():
            setattr(self, attr, value)
        
        self.text_pos = idx + count
        
        if self.TRACE:
            self.dump_state(idx, 'END')
            pprint_block(self.block)
    
    def end_block(self, idx, root_block = True):  
        if self.TRACE:
            self.dump_state(idx, 'BLOCK')
            pprint_block(self.block)
              
        if self.in_code:
            # Code coldn't be finished here
            return
        
        for (attr, default) in self.default_state.items():
            value = getattr(self, attr)
            if value != default:
                msg = 'Invalid state: %s = %s' % (attr, value)
                self._error(idx, msg)
                setattr(self, attr, default)
        
        self.end_text(idx)
        
        self.list_levels = {}
        if self.list_parent is not None:
            self.block = self.list_parent
            self.list_blocks = {}
            self.list_parent = None
        
        if self.incut:
            if self.block is not self.incut and not self.table_block:
                self.incut.add(self.block)
            self.block = self.incut
            return
        
        if root_block:
            if self.block.parts:
                self.blocks.append(self.block)
            
            self.block = Paragraph()
    
    def code_block(self, count, idx):
        if self.in_code:
            self.in_code = False
            self.end_block(idx)
        else:
            self.end_block(idx)
            self.block = Code()
            self.in_code = True
        self.text_pos += count
    
    def code_listing_block(self, count, idx):
        # TODO: group
        
        # Parse parameters
        nlidx = self.text.find('\n', idx + count)
        params = self.text[idx+count+1:nlidx]
        params = params.split()
        
        self.end_block(idx)
        
        # Read code from file if possible
        fname = params[0]
        code = ''
        with open(fname) as f:
            code = f.read()
        
        # Append as block
        block = CodeListing(os.path.basename(fname))
        block.add(code)
        
        self.blocks.append(block)
        
        # Ignore code listing text
        self.text_pos = nlidx
        
        return nlidx
    
    def incut_block(self, count, idx, incut):
        self.end_block(idx)
        if not self.incut:
            self.incut = self.block = Incut(incut[0])
        else:
            self.incut = None
        self.text_pos += count
    
    def _filter_escape(self, etext):
        idx = 0
        ftext = ''
        
        for eidx in self._escape:
            eidx -= self.text_pos            
            ftext += etext[idx:eidx]
            idx = eidx + 1
            
        ftext += etext[eidx + 1:]
        
        return ftext
    
    _dump_info = [ ('escape_pos', lambda pos: pos >= 0),
                   ('_escape', bool),
                   ('block_nl_pos', lambda pos: pos >= 0),
                   ('header_size', lambda pos: pos >= 0),
                   ('list_level', lambda pos: pos >= 0),
                   ('in_code', bool),
                   ('bold_char', bool),
                   ('italic_char', bool),
                   ('icode_cnt', lambda pos: pos >= 0),
                   ('link_pos', lambda pos: pos >= 0),
                   ('link_image', bool),
                   ('link_text_end', lambda pos: pos >= 0),
                   ('link_end_char', bool),
                   ('link_type', lambda pos: pos >= 0),
                   ('block_quote', bool)
                  ]
    
    def dump_state(self, idx, opttext = ''):
        # For debug purposes
        if idx >= len(self.text):
            return
        
        text_len = min(10, idx-self.text_pos)
        text_len = max(text_len, 0)
        chunk = self.text[idx:idx+text_len]
        
        print '%4s %3d %3d %3d %3d:%3d %s ' % (
                repr(self.text[idx]), 
                idx, self.text_pos, self.newline_pos,
                len(self.blocks), len(self.block.parts),
                repr(chunk)),

        for (attr, pred) in self._dump_info:
            value = getattr(self, attr)
            if pred(value):
                print '%s=%s ' % (attr, value),
        
        print opttext

class MiniMarkdownParser(MarkdownParser):
    def parse(self):
        idx = 0
        length = len(self.text)
        
        while idx < length:
            char = self.text[idx]
            
            if self.TRACE:
                self.dump_state(idx)
            
            try:
                idx = self._parse_at(idx, char)
            except Exception as e:
                self._error(idx, e)
            
            continue
        
        self.end_text(idx)
                                    
        return self.block.parts

if __name__ == "__main__":
    import sys
    
    _ = sys.argv.pop(0)    
    if sys.argv:
        fp = file(sys.argv[0])
        text = fp.read()
        fp.close()
    else:
        text = """

# Recommendation
Use [Google](http://google.com/) to search for **Information**
_Inline_ blocks are also good. Such as `` `code` `` or ` 'code' `

Some __lorem_ipsum__ stuff here. [Lorem Ipsum]
This is \_escaped thing. Escaping: \\\\
[Tag] Ouch!

### List

* 1
  * A
* 2

```
int a = 777;
    ```

!!! DEF
---
1 | 2
3 | 4
---
!!!
        """

    MarkdownParser.TRACE = True
    
    parser = MarkdownParser(text)    
    blocks = parser.parse()
    
    print '-----------------'
    
    for block in blocks:
        pprint_block(block)