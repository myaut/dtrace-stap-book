import string

from StringIO import StringIO

from tsdoc.blocks import *

class HTMLPrinter(Printer):
    single_doc = False
    
    NAV_HOME_TEXT = 'Home'
    
    NAV_LINKS = [(NavLink.PREV, 'pull-left', 'Prev'),
                 (NavLink.UP, 'pull-center', 'Up'),
                 (NavLink.REF, 'pull-center', 'Reference'),
                 (NavLink.NEXT, 'pull-right', 'Next')]
    
    INCUT_CLASSES = { 'DEF' : 'alert alert-success',
                      'WARN' : 'alert',
                      'INFO': 'alert alert-info',
                      'DANGER': 'alert alert-error' }
    
    def __init__(self, template_path):
        template_file = file(template_path, 'r')
        self.template = string.Template(template_file.read())
        template_file.close()
    
    def do_print(self, stream, header, page):
        self.real_stream = stream
        self.stream = StringIO()
        
        for block in page:
            self._print_block(block)
            
        body = self.stream.getvalue()
        navbar = self._gen_navbar(page)
        
        text = self.template.substitute(TITLE = header,
                                        BODY = body,
                                        NAVBAR = navbar,
                                        GENERATOR = 'TSDoc 0.2',
                                        HEADER = '<!-- HEADER -->',
                                        TAIL = '<!-- TAIL -->',
                                        RELPATH = '../' if page.docspace else '')
        
        self.real_stream.write(text)
        
        self.stream.close()
    
    def _gen_navbar(self, page):
        nav_home = ''
        nav_links = []
                
        if NavLink.HOME in page.nav_links:
            nav_link = page.nav_links[NavLink.HOME]
            nav_home = '<a class="brand" href="%s">%s</a>' % (nav_link.where, 
                                                              nav_link.page.header)
        
        for nav_type, nav_class, nav_text in HTMLPrinter.NAV_LINKS:
            if nav_type in page.nav_links:
                nav_link = page.nav_links[nav_type]
                
                text = '<strong>' + nav_text + '</strong>' 
                
                if nav_type != NavLink.REF:
                    text += '(%s)' % nav_link.page.header
                
                nav_code = '<ul class="nav %s">\n' % nav_class
                nav_code += '<li><a href="%s">%s</a></li>' % (nav_link.where, 
                                                              text)
                nav_code += '\n</ul>'
                
                nav_links.append(nav_code)
        
        return nav_home + '\n'.join(nav_links) 
    
    def _html_filter(self, block, s):
        if isinstance(block, Code):
            s = self._fix_tab_stops(s)
        
        s = s.replace('<', '&lt;')
        s = s.replace('>', '&gt;')
        
        if not isinstance(block, Code):
            s = s.replace('\n', '<br />')
        
        return s
    
    def _print_block(self, block, indent = 0):
        block_tags = [] 
        in_code = False
        
        if isinstance(block, Paragraph):
            block_tags.append(('p', None))
        if isinstance(block, Code):
            block_tags.append(('pre', None))
            in_code = True
        elif isinstance(block, ListEntry):
            block_tags.append(('li', None))
        elif isinstance(block, ListBlock):
            block_tags.append(('ul', None))
        elif isinstance(block, Table):
            block_tags.append(('table', 'class="table"'))
        elif isinstance(block, TableRow):
            block_tags.append(('tr', None))
        elif isinstance(block, TableCell):
            attrs = ''
            if block.colspan > 1:
                attrs += ' colspan="%d"' % block.colspan
            if block.rowspan > 1:
                attrs += ' rowspan="%d"' % block.rowspan
            
            block_tags.append(('td', attrs))
        elif isinstance(block, BlockQuote):
            block_tags.append(('blockquote', None))
        elif isinstance(block, Incut):
            _class = HTMLPrinter.INCUT_CLASSES[block.style]
            block_tags.append(('div', 'class="{}"'.format(_class)))
        
        for tag, attrs in block_tags:
            self.stream.write(' ' * indent)
            if attrs:
                self.stream.write('<%s %s>\n' % (tag, attrs))
            else:
                self.stream.write('<%s>\n' % (tag))
        
        text = ''
        list_stack = []
        for part in block:
            if isinstance(part, Block):
                self._print_block(part, indent + 4)
            else:
                tag = None
                tag_attrs = {}
                
                if isinstance(part, Header):
                    tag = 'h%d' % part.size
                elif isinstance(part, ItalicText):
                    tag = 'em'
                elif isinstance(part, BoldText):
                    tag = 'strong'
                elif isinstance(part, InlineCode):                    
                    tag = 'code'
                elif isinstance(part, Label):                    
                    tag = 'span'
                    tag_attrs["class"] = "label label-%s" % part.style
                elif isinstance(part, Reference):
                    tag = 'a'
                    tag_attrs['name'] = part.text
                    part.text = ''
                elif isinstance(part, Image):
                    # XXX: very dependent on book's directory structure
                    tag = '<img src="{}" alt="{}" />'.format('../images/' + part.where, text)
                    self.stream.write(tag)
                    continue
                elif isinstance(part, Link):
                    tag = 'a'
                    tag_attrs['href'] = part.where
                    
                    if part.type == Link.INVALID:
                        tag_attrs['style'] = "color: red"
                
                text = self._html_filter(block, str(part))
                
                if tag:
                    attr_str = ' '.join('%s="%s"' % (attr, value)
                                        for attr, value
                                        in tag_attrs.items())
                    if attr_str:
                        attr_str = ' ' + attr_str
                        
                    text = '<%s%s>' % (tag, attr_str) + text + '</%s>' % (tag)                
                
                text = text.replace('\t', ' ' * Printer.TAB_STOPS)
                
                # if not in_code:
                #    self.stream.write('\n' + ' ' * indent)
                self.stream.write(text)
        
        for (tag, attrs) in reversed(block_tags):
            self.stream.write('</%s>\n' % tag)