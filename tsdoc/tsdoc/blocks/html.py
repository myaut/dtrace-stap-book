import sys
import string
import os

from StringIO import StringIO

from tsdoc.blocks import *

import PIL

class HTMLPrinter(Printer):
    single_doc = False
    
    NAV_HOME_TEXT = 'Home'
    
    FLOATING_DIV_BASE_WIDTH = 700
    FLOATING_DIV_BASE_PCT = 108
    SPACER_BASE_HEIGHT = 2400
    
    NAV_LINKS = [(NavLink.PREV, 'pull-left', 'Prev'),
                 (NavLink.UP, 'pull-center', 'Up'),
                 (NavLink.REF, 'pull-center', 'Reference'),
                 (NavLink.NEXT, 'pull-right', 'Next')]
    
    INCUT_CLASSES = { 'DEF' : ('label label-inverse', 'Definition'),
                      'WARN' : ('label label-warning', 'Warning'),
                      'INFO': ('label label-info', 'Information'),
                      'NOTE': ('label label-info', 'Note'),
                      'DANGER': ('label label-important', 'DANGER!') }
    
    IMAGE_PATH = os.environ.get('TSDOC_IMGDIR')
    
    def __init__(self, template_path):
        template_file = file(template_path, 'r')
        self.template = string.Template(template_file.read())
        
        self._relpath = None
        self._image_scale = None
        
        template_file.close()
    
    def do_print(self, stream, header, page):
        self.real_stream = stream
        self.block_idx_gen = iter(xrange(sys.maxint))
        self.stream = StringIO()
        
        self._relpath = '../' if page.docspace else ''
        
        for block in page:
            self._print_block(block)
            
        body = self.stream.getvalue()
        navbar_top = self._gen_navbar(page, True)
        navbar_bottom = self._gen_navbar(page, False)
        
        text = self.template.substitute(TITLE = header,
                                        BODY = body,
                                        NAVBAR_TOP = navbar_top,
                                        NAVBAR_BOTTOM = navbar_bottom,
                                        GENERATOR = 'TSDoc 0.2',
                                        HEADER = '<!-- HEADER -->',
                                        TAIL = '<!-- TAIL -->',
                                        RELPATH = self._relpath)
        
        self.real_stream.write(text)
        
        self.stream.close()
    
    def _gen_navbar(self, page, brand_link):
        nav_home = ''
        nav_links = []
                
        if NavLink.HOME in page.nav_links:
            if brand_link:
                nav_link = page.nav_links[NavLink.HOME]
                nav_home = '<a class="brand" href="%s">%s</a>' % (nav_link.where, 
                                                                  nav_link.page.header)
            elif NavLink.UP not in page.nav_links:
                page.nav_links[NavLink.UP] = page.nav_links[NavLink.HOME]
        
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
        # FIXME: Allow to use raw HTML in Code (breaks compatibility with other printers!)
        if isinstance(block, Code):
            s = self._fix_tab_stops(s)
            
            s = s.replace('\\<', '&lt;')
            s = s.replace('\\>', '&gt;')
        else:
            s = s.replace('<', '&lt;')
            s = s.replace('>', '&gt;')
        
        
        return s
    
    def _print_block(self, block, indent = 0, codeid = None):
        block_tags = [] 
        in_code = False
        
        if isinstance(block, Paragraph):
            block_tags.append(('p', None))
        elif isinstance(block, Header):
            block_tags.append(('h%d' % block.size, None))
        if not codeid and isinstance(block, CodeListing):
            block_tags.append(('div', 'class="well"'))
        elif isinstance(block, Code):
            block_tags.append(('pre', None if not codeid 
                                      else 'id="code%d" class="hide"' % codeid))
            in_code = True
        elif isinstance(block, ListEntry):
            block_tags.append(('li', None))
        elif isinstance(block, ListBlock):
            block_tags.append(('ul', None))
        elif isinstance(block, Table):
            attr = 'class="table table-bordered"'
            if block.colwidths is not None:
                # Do not make width of every column strict
                attr += ' style="width: %d%%"' % int(100 * sum(block.colwidths))
            
            block_tags.append(('table', attr))
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
        elif isinstance(block, FlowableIncut):
            style = 'position: absolute; '
            if 'x' in block.coords:
                x = block.coords['x'] * self.FLOATING_DIV_BASE_PCT
                style += 'left: {0:.1f}%; '.format(x)
            if 'w' in block.coords:
                w = block.coords['w'] * self.FLOATING_DIV_BASE_WIDTH
                style += 'width: {0:.1f}px; '.format(w)
            if 'y' in block.coords:
                y = block.coords['y'] * self.SPACER_BASE_HEIGHT
                style += 'margin-top: {0:.1f}px; '.format(y)
            if 's' in block.coords:
                self._image_scale = block.coords['s']
            
            block_tags.append(('div', 'style="{0}"'.format(style)))
        elif isinstance(block, PageSpacer):
            if block.iscond:
                return
            h = block.height * self.SPACER_BASE_HEIGHT
            block_tags.append(('div', 'style="height: {0:.1f}px"'.format(h)))
        elif isinstance(block, Incut):
            block_tags.append(('div', 'class="well"'))
            
            _class, label = HTMLPrinter.INCUT_CLASSES[block.style]
            self.stream.write('<span class="%s">%s</span>' % (_class, label))
        elif isinstance(block, Span):
            if block.style == 'small':
                block_tags.append(('small', None))
            elif block.style[0] == '#':
                block_tags.append(('span', 'style="color: {0};"'.format(block.style[1:])))
        
        for tag, attrs in block_tags:
            self.stream.write(' ' * indent)
            if attrs:
                self.stream.write('<%s %s>\n' % (tag, attrs))
            else:
                self.stream.write('<%s>\n' % (tag))
        
        if not codeid and isinstance(block, CodeListing):
            # Embedded codelisting
            fname = os.path.basename(block.fname)
            blockid = next(self.block_idx_gen) + 1
            self.stream.write('<button class="btn" onclick="toggleCode(\'code%s\')">+</button>' % (blockid))
            self.stream.write('&nbsp; Script file %s <br/>' % (fname))
            self._print_block(block, codeid = blockid)
        else:
            self._print_parts(block, indent)
        
        for (tag, attrs) in reversed(block_tags):
            self.stream.write('</%s>\n' % tag)
        
        if isinstance(block, FlowableIncut) and 's' in block.coords:
            self._image_scale = None
        
    def _print_parts(self, block, indent):
        text = ''
        list_stack = []
        for part in block:
            if isinstance(part, Block):
                self._print_block(part, indent + 4)
            else:
                tag = None
                tag_attrs = {}
                text = self._html_filter(block, str(part))
                
                if isinstance(part, ItalicText):
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
                    tag_attrs['name'] = part.get_name()
                    text = ''
                elif isinstance(part, Image):
                    # XXX: very dependent on book's directory structure

                    tag = 'img'
                    tag_attrs['src'] = self._relpath + 'images/' + part.where
                    tag_attrs['alt'] = text
                    tag_attrs['class'] = 'img-rounded'
                    if self._image_scale:
                        image = PIL.Image.open(os.path.join(self.IMAGE_PATH, part.where))
                        imgwidth, imgheight = image.size
                        tag_attrs['width'] = imgwidth * self._image_scale
                        tag_attrs['height'] = imgheight * self._image_scale
                    
                    text = ''
                elif isinstance(part, Link):
                    tag = 'a'
                    tag_attrs['href'] = part.where
                    
                    if part.type == Link.INVALID:
                        tag_attrs['style'] = "color: red"
                elif isinstance(part, BreakLine):
                    self.stream.write('<br />')
                    continue
                
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