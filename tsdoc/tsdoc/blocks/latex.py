import string

from tsdoc.blocks import *

class LatexPrinter(Printer):
    single_doc = True
    
    LATEX_PACKAGES = ['listings', 'xcolor', 'fullpage', 'hyperref', 'csquotes']
    
    BTAG_BEGINEND = 0
    BTAG_CONTAINER = 1
    BTAG_ALONE = 2
    
    LISTING_PARAMS = {'language':       'C',
                      'breaklines':     'true',
                      'backgroundcolor':'\\color{lightgray!20}',
                      'basicstyle':     '\\footnotesize',
                      'xleftmargin':    '\\parindent',
                      'xrightmargin':    '\\parindent',
                      'framesep':    '5pt',
                      'frame':    'single'
                      }
    
    HYPERPARAMS = { 'pdftex' : None,
                    'hidelinks': 'true',
                    'colorlinks' : 'true',
                    'linkcolor' : '{red!50!black}',                    
                    'urlcolor':'{blue!80!black}'
                   }
    
    def __init__(self):
        self.pages = []
    
    def do_print_pages(self, stream, header, pages):
        self.stream = stream
        
        stream.write('\\documentclass[10pt]{book}\n\n')
        
        for pkg in LatexPrinter.LATEX_PACKAGES:
            stream.write('\\usepackage{%s}\n' % pkg)
                
        self._setup_package('lstset', LatexPrinter.LISTING_PARAMS)
        self._setup_package('hypersetup', LatexPrinter.HYPERPARAMS)
        
        stream.write('\\begin{document}\n\n')
        
        for page in pages:
            stream.write('\n\\hypertarget{%s}{}\n' % page.name)
            
            for block in page:
                self._print_block(page, block)
                
            stream.write('\\newpage')
                
        stream.write('\n\n\\end{document}')
    
    def _setup_package(self, tag, params):
        param_str = ', '.join('%s=%s' % (k, v) if v else k 
                              for k, v 
                              in params.items())
        
        self.stream.write('\\%s{%s}\n\n' % (tag, param_str))
    
    def _latex_filter(self, block, s):
        if not s:
            return s
        
        if isinstance(block, Code):
            s = self._fix_tab_stops(s)            
        else:
            s = s.replace('\\', '\\textbackslash ')
            s = s.replace('{', '\\{')
            s = s.replace('}', '\\}')
            s = s.replace('_', '\\_')
            s = s.replace('&', '\\&')
            s = s.replace('*', '\\*')
            s = s.replace('$', '\\$')
            s = s.replace('#', '\\#')
        
        return s
    
    def _print_block(self, page, block):
        block_tags = [] 
        in_code = False
        
        if isinstance(block, Paragraph):
            self.stream.write('\n    ')
        if isinstance(block, Code):
            block_tags.append(('lstlisting', LatexPrinter.BTAG_BEGINEND))
            in_code = True
        elif isinstance(block, ListEntry):
            block_tags.append(('item', LatexPrinter.BTAG_ALONE))
        elif isinstance(block, ListBlock):
            block_tags.append(('itemize', LatexPrinter.BTAG_BEGINEND))
            block_tags.append(('itemsep0pt', LatexPrinter.BTAG_ALONE))
            block_tags.append(('parsep0pt', LatexPrinter.BTAG_ALONE))
            block_tags.append(('parskip0pt', LatexPrinter.BTAG_ALONE))
        elif isinstance(block, Table):
            return
            block_tags.append(('tabular', LatexPrinter.BTAG_BEGINEND))
        elif isinstance(block, BlockQuote):
             block_tags.append(('blockquote', LatexPrinter.BTAG_CONTAINER))
        
        for tag, tagtype in block_tags:
            if tagtype == LatexPrinter.BTAG_BEGINEND:
                self.stream.write('\\begin{%s}\n' % (tag))
            elif tagtype == LatexPrinter.BTAG_ALONE:
                self.stream.write('\\%s ' % (tag))
            elif tagtype == LatexPrinter.BTAG_CONTAINER:
                self.stream.write('\\%s{' % (tag))
        
        self._print_block_content(page, block)
        
        for tag, tagtype in reversed(block_tags):
            if tagtype == LatexPrinter.BTAG_BEGINEND:
                self.stream.write('\\end{%s}\n' % (tag))
            elif tagtype == LatexPrinter.BTAG_CONTAINER:
                self.stream.write('}\n')
        
        if isinstance(block, Paragraph):
            self.stream.write('\n')
    
    def _make_link(self, s):
        s = s.replace('.tex', '')
        
        s = filter(lambda c: c in string.letters + '/#', s)
        s = s.replace('/', ':')
        s = s.replace('#', ':')
        
        return s
    
    def _print_block_content(self, page, block):
        text = ''
        list_stack = []
        for part in block:
            if isinstance(part, Block):
                self._print_block(page, part)
            else:
                tag = None
                tag_attrs = {}
                do_filter = True
                
                text = str(part)
                
                if not text:
                    continue
                
                if isinstance(part, LineBreak):
                    self.stream.write(' \\\\\n ')
                    continue
                
                if isinstance(part, Header):
                    if part.size == 1:
                        tag = 'Huge'
                    elif part.size == 2:
                        tag = 'huge'
                    elif part.size == 3:
                        tag = 'LARGE'
                    elif part.size == 4:
                        tag = 'Large'
                    elif part.size == 5:
                        tag = 'large'
                    else:
                        tag = 'textit'
                    
                    self.stream.write('\\vspace{10 mm}  {\\%s  \\textbf {' % tag)
                    self.stream.write(self._latex_filter(block, str(part)))
                    self.stream.write('}} \n\n')
                    
                    continue
                
                if isinstance(part, ItalicText):
                    tag = 'textit'
                elif isinstance(part, BoldText):
                    tag = 'textbf'
                elif isinstance(part, InlineCode):                    
                    tag = 'texttt'
                elif isinstance(part, Label):                    
                    tag = 'fbox'
                elif isinstance(part, Reference):
                    ref = page.name + ':' + self._make_link(text)
                    text = ''
                    tag = 'hypertarget{%s}' % ref
                    do_filter = False
                elif isinstance(part, Link):
                    if part.type == Link.EXTERNAL:
                        if not part.where.startswith('http'):
                            part.type = Link.INTERNAL
                        else:
                            tag='href{%s}' % part.where
                    
                    if part.type == Link.INTERNAL:
                        ref = self._make_link(part.where)
                        tag='hyperlink{%s}' % ref
                        
                if do_filter:
                    text = self._latex_filter(block, text)
                
                print text
                
                if tag:
                    attr_str = ' '.join('%s="%s"' % (attr, value)
                                        for attr, value
                                        in tag_attrs.items())
                    if attr_str:                    
                        attr_str = '[' + attr_str + ']'
                    
                    text = '\\%s %s {' % (tag, attr_str) + text + '} '         
                
                text = text.replace('\t', ' ' * Printer.TAB_STOPS)
                
                self.stream.write(text)
                
                