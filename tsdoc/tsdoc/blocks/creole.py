import string

from tsdoc.blocks import *

class CreolePrinter(Printer):
    single_doc = False
    
    def __init__(self):
        pass    
    
    def do_print(self, stream, header, page):
        self.stream = stream
        
        for block in page:
            self._print_block(block)
    
    def _creole_filter(self, block, s):
        if isinstance(block, Code):
            return s
        
        # s = s.replace('_', '\\_')
        # s = s.replace('*', '\\*')
        
        if isinstance(block, BlockQuote):
            l = s.split('\n')
            L = []
            for l in s:
                L.append('> ' + l)
            s = '\n'.join(L)        
        elif not isinstance(block, Code):
            s = s.replace('\n', ' ')
                    
        return s
    
    def _print_block(self, block):
        if isinstance(block, Paragraph):
            self.stream.write('\n\n')
        if isinstance(block, Code):
            self.stream.write('\n{{{\n')
        elif isinstance(block, ListEntry):
            self.stream.write('\n' + '*' * block.level + '   ')
        
        text = ''
        for part in block:
            if isinstance(part, Block):
                self._print_block(part)
            else:
                prefix = ''
                suffix = ''
                
                if isinstance(part, Header):
                    prefix = suffix = ' ' + '=' * part.size + ' '
                elif isinstance(part, ItalicText):
                    prefix = suffix = '//'
                elif isinstance(part, BoldText):
                    prefix = suffix = '**'
                elif isinstance(part, InlineCode):                    
                    prefix = suffix = '`'
                elif isinstance(part, Reference):
                    prefix = '['
                    suffix = ']'
                elif isinstance(part, Link):
                    suffix = ']]'
                    prefix = '[[%s|' % part.where
                
                text = self._creole_filter(block, str(part))
                text = prefix + text + suffix
                
                self.stream.write(text)
        
        if isinstance(block, Code):
            self.stream.write('\n}}}\n')
        if isinstance(block, Paragraph):
            self.stream.write('\n\n')