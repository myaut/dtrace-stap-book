import string

from tsdoc.blocks import *

class MarkdownPrinter(Printer):
    single_doc = False
    
    def __init__(self):
        pass    
    
    def do_print(self, stream, header, page):
        self.stream = stream
        for block in page:
            self._print_block(block)
    
    def _md_filter(self, block, s):
        if isinstance(block, Code):
            return s
        
        s = s.replace('_', '\\_')
        s = s.replace('*', '\\*')
        
        return s
    
    def _last_newline(self, text):
        for char in reversed(text):
            if char not in string.whitespace:
                return False
            
            if char == '\n':
                return True
        
        return False
    
    def _print_block(self, block):
        if isinstance(block, Paragraph):
            self.stream.write('\n')
        if isinstance(block, Code):
            self.stream.write('\n```\n')
        elif isinstance(block, ListEntry):
            self.stream.write(' ' * block.level + ' * ')
        
        text = ''
        for part in block:
            if isinstance(part, Block):
                self._print_block(part)
            else:
                prefix = ''
                suffix = ''
                
                if isinstance(part, Header):
                    prefix = '#' * part.size + ' '
                    suffix = '\n'
                elif isinstance(part, ItalicText):
                    prefix = suffix = '_'
                elif isinstance(part, BoldText):
                    prefix = suffix = '**'
                elif isinstance(part, InlineCode):                    
                    prefix = suffix = '`'
                elif isinstance(part, Reference):
                    prefix = '['
                    suffix = ']'
                elif isinstance(part, Link):
                    prefix = '['
                    
                    if part.type == Link.INTERNAL:
                        suffix = '][%s]' % part.where
                    else:
                        suffix = '](%s)' % part.where
                
                text = self._md_filter(block, str(part))
                text = prefix + text + suffix
                
                self.stream.write(text)
        
        if isinstance(block, ListEntry):
            if not self._last_newline(text):
                self.stream.write('\n')
        elif isinstance(block, Code):
            self.stream.write('\n```\n')
        if isinstance(block, Paragraph):
            self.stream.write('\n')