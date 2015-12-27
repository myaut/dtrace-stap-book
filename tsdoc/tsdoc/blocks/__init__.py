'''
TSDoc blocks

intermediate doc representation before gerating HTML/Markdown/etc.

Two main classes:
    - Block - block of text, contains other blocks, and text in array
    - Text - represents any text (for plain text use __str__)
By default renders into plain text via __str__, use tsdoc.printer, to
create formatted text.

For example:

Block(Header(1, "Recomendation"]),
      Paragraph(['Use', Link('Google', 'http://google.com/'),
                 'to search for', BoldText('Information')]),
      Code('int a = 777;'))

is matches with this text

# Recomendation

Use [Google](http://google.com/) to search for **Information**

```
int a = 777;
```

'''

import sys

class LineBreak(object):
    def __str__(self):
        return '\n'

class Text(object):
    def __init__(self, text):
        self.text = text
    
    def __str__(self):
        return self.text
    
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, 
                           repr(self.text))

class BreakLine(Text):
    def __init__(self, text):
        Text.__init__(self, '')

class BoldText(Text):
    pass

class ItalicText(Text):
    pass

class BoldItalicText(Text):
    pass

class InlineCode(Text):
    pass

class Reference(Text):
    def __str__(self):
        return ''

class CodeReference(Reference):
    def __init__(self, text, ref_name, ref_class):
        Reference.__init__(self, text.replace(' ', '_'))
        
        self.ref_name = ref_name
        self.ref_class = ref_class

class Label(Text):
    def __init__(self, text, style):
        Text.__init__(self, text)
        self.style = style
        
    def __repr__(self):
        return 'Label(%s, %s)' % (repr(self.style), 
                                  repr(self.text)) 

class Link(Text):
    INTERNAL = 0
    EXTERNAL = 1
    INVALID = 2
    
    def __init__(self, text, type, where):
        Text.__init__(self, text)
        self.type = type
        self.where = where
        
    def __repr__(self):
        return '%s(%d, %s, %s)' % (self.__class__.__name__,
                                   self.type, repr(self.where), 
                                   repr(self.text))

class Image(Link):
    pass

class Block(object):
    def __init__(self, parts = []):
        if parts:
            self.parts = parts
        else:
            self.parts = []
    
    def add(self, text):
        self.parts.append(text)
        
    def extend(self, text_list):
        self.parts.extend(text_list)
        
    def __iter__(self):
        return iter(self.parts)

class Header(Block):
    def __init__(self, size, parts = []):
        self.size = size
        Block.__init__(self, parts)

class ListEntry(Block):
    def __init__(self, level, parts = []):
        self.level = level
        Block.__init__(self, parts)

class ListBlock(Block):
    pass

class Paragraph(Block):
    pass

class Code(Paragraph):
    pass

class Table(Block):
    pass

class TableRow(Block):
    pass

class TableCell(Block):
    def __init__(self, colspan = 1, rowspan = 1, parts = []):
        Block.__init__(self, parts)
        
        self.colspan = colspan
        self.rowspan = rowspan

class BlockQuote(Paragraph):
    pass

class CodeListing(Code):
    def __init__(self, fname = '', parts = []):
        Code.__init__(self, parts)
        
        self.fname = fname

class Incut(Block):
    def __init__(self, style, parts = []):
        Block.__init__(self, parts)
        
        self.style = style
    
class NavLink(object):
    PREV = 0
    NEXT = 1
    UP   = 2
    HOME = 3
    REF  = 4
    
    def __init__(self, type, page, where):
        self.type = type
        self.page = page
        self.where = where

def pprint_block(block, stream = sys.stdout, indent = 0):
    def do_print(s):
        print >> stream, ' ' * indent, s,
        
    prefix = '%s(%s\n' % (block.__class__.__name__,
                          ', '.join('%s=%s' % (attr, repr(getattr(block, attr)))
                                    for attr in dir(block)
                                    if (attr[0] != '_' and 
                                        attr not in ['parts', 'text'] and 
                                        not callable(getattr(block, attr))) ))
    do_print(prefix)
    
    indent += len(block.__class__.__name__) + 1
    
    for part in block:
        if isinstance(part, Block):
            pprint_block(part, stream, indent)
        else:
            do_print(repr(part) + ',\n')
    
    do_print(')\n')
        
        
class Printer:
    TAB_STOPS = 4
    
    def _fix_tab_stops(self, text):
        lines = []
        for line in text.split('\n'):
            start_idx = idx = 0
            new_line = ''
            
            while idx != -1:
                idx = line.find('\t', start_idx)
                if idx > 0:
                    if line[idx - 1] == '\t':
                        count = Printer.TAB_STOPS
                    else:
                        count = Printer.TAB_STOPS - idx % Printer.TAB_STOPS
                    new_line += line[start_idx:idx] + " " * count
                    start_idx = idx + 1
                else:
                    break
                
            new_line += line[start_idx:]
            lines.append(new_line)
        
        return '\n'.join(lines)        
    
    def do_print(self, stream, header, page):
        pass
    
    def do_print_pages(self, stream, header, pages):
        pass