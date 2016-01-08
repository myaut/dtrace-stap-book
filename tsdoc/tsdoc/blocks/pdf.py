import os
import re
import string

import cStringIO

import PIL

from tsdoc.blocks import *

from reportlab.rl_config import defaultPageSize
from reportlab.platypus import (Paragraph, Preformatted, SimpleDocTemplate, 
                                PageBreak, Spacer, KeepTogether, Flowable, 
                                CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus import Table as RLTable
from reportlab.platypus import Image as RLImage

from reportlab.pdfbase.pdfmetrics import stringWidth

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import enums, colors, pagesizes

class _PageInfoFlowable(Flowable):
    # This flowable incapsulates TSDoc pages. It is not shown on canvas
    # but used for generating table of contents
    def __init__(self, page, info):
        self.info = info
        self.page = page
        
        self.width = 0
        self.height = 0
    
    def draw(self):
        pass

class _ListingInfoFlowable(Flowable):
    def __init__(self, fname):
        self.fname = fname
        
        self.width = 0
        self.height = 0
    
    def draw(self):
        pass

class ListOfListings(TableOfContents):
    def __init__(self, ext):
        self.ext = re.compile(r'([^.]*)\.' + ext)
        return TableOfContents.__init__(self)
    
    def notify(self, kind, stuff):
        if kind == 'TOCListing':
            fname = stuff[1]
            if self.ext.match(fname):
                self.addEntry(*stuff)

class _TSDocTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, _PageInfoFlowable):
            if flowable.info:
                level, header = flowable.info
            else:
                header = flowable.page.header
                level = 1
                
                if hasattr(flowable.page, 'is_external'):
                    level = 0
                    self.header = header
                
            self.notify('TOCEntry', (level, header, self.page))
        
        if isinstance(flowable, _ListingInfoFlowable):
            self.notify('TOCListing', (1, flowable.fname, self.page))
        
    def handle_documentBegin(self):
        self.canv.setTitle(os.environ['TSDOC_HEADER'])
        self.canv.setAuthor(os.environ['TSDOC_AUTHOR'])
        
        self.header = ''
        
        return SimpleDocTemplate.handle_documentBegin(self)
    
    def handle_pageEnd(self):
        if self.page < 2:
            return SimpleDocTemplate.handle_pageEnd(self)
        
        canv = self.canv
        
        W, H = defaultPageSize
        w, h = W / 3, pagesizes.inch
        padding = pagesizes.inch
        
        # Draw line
        canv.saveState()
        canv.setStrokeColorRGB(0, 0, 0)
        canv.setLineWidth(0.5)
        canv.line(padding, h, W - padding, h)
        canv.restoreState()
        
        # Draw page number & header
        rtext, ltext = str(self.page), self.header
        if (self.page % 2) == 0:
            rtext, ltext = ltext, rtext
        
        style = ParagraphStyle('footer-base', fontName='Times-Roman', 
                               leading=12, fontSize=10)
        right = Paragraph(rtext, 
                          style=ParagraphStyle('footer-right', 
                                                parent=style, alignment=enums.TA_RIGHT))
        left = Paragraph(ltext,
                         style=ParagraphStyle('footer-left',
                                              parent=style, alignment=enums.TA_LEFT))
        
        pw, ph = right.wrapOn(canv, w, h)
        right.drawOn(canv, W - padding - pw, h - ph)
        
        pw, ph = left.wrapOn(canv, w, h)
        left.drawOn(canv, padding, h - ph)
        
        return SimpleDocTemplate.handle_pageEnd(self)
    
class PDFPrinter(Printer):
    single_doc = True
    xref_pages = False
    
    PAGE_WIDTH, PAGE_HEIGHT = defaultPageSize           
    
    IMAGE_DPI = 120
    IMAGE_PATH = 'build/images'
    MAX_INLINE_IMAGE_SIZE = 64
    
    RIGHT_ARROW = u"\u2192".encode('utf-8')
    MAX_CODE_LINE_LEN = 80
    MAX_CODE_LINE_WIDTH = PAGE_WIDTH * 0.8
    
    CODE_REPLACE = [
        ('\t', '    '),
        ('<b>', ''),
        ('</b>', ''),
        ('<i>', ''),
        ('</i>', ''),
        ]
    
    TOC_LEVELS = {2: 1,
                  5: 2}
    
    INCUT_CLASSES = { 'DEF' : 'Definition',
                      'WARN' : 'Warning',
                      'INFO':  'Information',
                      'NOTE': 'Note',
                      'DANGER': 'DANGER!' }
    
    SOURCE_URL = 'https://raw.githubusercontent.com/myaut/dtrace-stap-book/master/'
    
    def __init__(self):
        # Dictionary page name -> header/level used for generating TOCs
        self._page_info = {}
        self._current_page = None
        
        self.print_sources = not os.environ.get('TSDOC_NO_SOURCES')
        
        self._create_styles()
    
    def _create_styles(self):
        default = ParagraphStyle(
                    'default',
                    fontName='Times-Roman',
                    fontSize=10,
                    leading=12,
                    leftIndent=0, rightIndent=0, firstLineIndent=0,
                    alignment=enums.TA_LEFT,
                    spaceBefore=0, spaceAfter=2,
                    bulletFontName='Times-Roman', bulletFontSize=10, bulletIndent=0,
                    textColor=colors.black, backColor=None,
                    wordWrap=None,
                    borderWidth=0, borderPadding=0,
                    borderColor=None, borderRadius=None,
                    allowWidows=1,
                    allowOrphans=0,
                    textTransform=None,
                    endDots=None,   
                    splitLongWords=1,
                )
        
        header = ParagraphStyle('header', parent=default, 
                                fontName='Times-Bold', alignment=enums.TA_LEFT)
        incut = ParagraphStyle('header', parent=default, 
                                alignment=enums.TA_CENTER, textColor=colors.white, 
                                fontName='Helvetica', fontSize=10)
        
        self._styles = {
            'default': default,
            
            'root': ParagraphStyle('root', parent=default, 
                                   fontSize=12, leading=14, firstLineIndent=8,
                                   alignment=enums.TA_JUSTIFY, spaceBefore=4, spaceAfter=4),
            
            'h1': ParagraphStyle('h1', parent=default, fontSize=32, leading=48),
            'h2': ParagraphStyle('h2', parent=default, fontSize=24, leading=36),
            'h3': ParagraphStyle('h3', parent=default, fontSize=20, leading=24),
            'h4': ParagraphStyle('h4', parent=default, fontSize=18, leading=24),
            'h5': ParagraphStyle('h5', parent=default, fontSize=16, leading=20),
            'h6': ParagraphStyle('h6', parent=default, fontSize=12, leading=14),
            
            'code': ParagraphStyle('code', parent=default,
                                   fontSize=10, fontName='Courier',
                                   backColor=colors.lightskyblue,
                                   borderWidth=2, borderColor=colors.skyblue),
            
            'incut-DEF': ParagraphStyle('incut-def', parent=incut, backColor=colors.darkgray),
            'codelisting': ParagraphStyle('codelisting', parent=incut, backColor=colors.darkgreen),
            'incut-INFO': ParagraphStyle('incut-info', parent=incut, backColor=colors.darkblue),
            'incut-NOTE': ParagraphStyle('incut-note', parent=incut, backColor=colors.darkslateblue),
            'incut-WARN': ParagraphStyle('incut-warn', parent=incut, backColor=colors.darkorange),
            'incut-DANGER': ParagraphStyle('incut-danger', parent=incut, backColor=colors.darkred),
            
            'blockquote': ParagraphStyle('blockquote', parent=default, leftIndent=20)
            }
        
    
    def do_print_pages(self, stream, header, pages):
        self.stream = stream
        
        paragraphs = []
        
        pages = iter(pages)
        self._print_index(paragraphs, next(pages), header)
        
        for page in pages:
            # In the beginning of new section -- add page break
            self._current_page = page
            if hasattr(page, 'is_external'):
                paragraphs.append(PageBreak())
                paragraphs.append(Spacer(self.PAGE_WIDTH,
                                         self.PAGE_HEIGHT / 5))
            
            paragraphs.append(_PageInfoFlowable(page, self._page_info.get(page.page_path)))            
            
            if hasattr(page, 'is_external'):
                paragraphs.append(Paragraph(page.header,
                                            style=self._styles['h2']))
                continue
            
            first = True
            for block in page:
                paragraphs.extend(self._print_paragraph(block, root=True, first=first))
                first = False
            
        doc = _TSDocTemplate(stream)
        doc.multiBuild(paragraphs)
    
    def _print_index(self, paragraphs, index, header):
        paragraphs.append(Spacer(self.PAGE_WIDTH, self.PAGE_HEIGHT / 4))
        paragraphs.append(Paragraph(header, self._styles['h1']))
        paragraphs.append(Spacer(self.PAGE_WIDTH, self.PAGE_HEIGHT / 5))
        
        blocks = iter(index)
        for block in blocks:
            if any(isinstance(part, Header) for part in block):
                break
            paragraphs.extend(self._print_paragraph(block, root=True))
            
        self._find_page_info(blocks)
        
        # Print table of contents. index.md contains 
        paragraphs.append(PageBreak())
        paragraphs.append(Paragraph('Table of contents', self._styles['h3']))
        self._add_toc(paragraphs, TableOfContents())
        
        # Generate list of listings
        if self.print_sources:
            paragraphs.append(PageBreak())
            paragraphs.append(Paragraph('SystemTap example scripts', self._styles['h3']))
            self._add_toc(paragraphs, ListOfListings(r'stp'))
            paragraphs.append(Paragraph('DTrace example scripts', self._styles['h3']))
            self._add_toc(paragraphs, ListOfListings(r'd$'))
            paragraphs.append(Paragraph('Other source files', self._styles['h3']))
            self._add_toc(paragraphs, ListOfListings('(?!d|stp)'))
    
    def _add_toc(self, paragraphs, toc):
        root = self._styles['root']
        
        toc.levelStyles = [
            ParagraphStyle('TOCHeading1', parent=root, 
                fontName='Times-Bold', fontSize=14,
                leftIndent=20, firstLineIndent=-20, spaceBefore=5, leading=16),
            ParagraphStyle('TOCHeading2', parent=root,
                leftIndent=40, firstLineIndent=-20, spaceBefore=0, leading=12),
            ParagraphStyle('TOCHeading3', parent=root,
                leftIndent=60, firstLineIndent=-20, spaceBefore=0, leading=12)
            ]
        
        paragraphs.append(toc)
    
    def _find_page_info(self, parts, level=1):
        for part in parts:
            if isinstance(part, ListEntry):
                level = self.TOC_LEVELS[part.level]
                
            if isinstance(part, Block):
                self._find_page_info(part.parts, level)
                
            if isinstance(part, Link) and part.type == Link.INTERNAL:
                self._page_info[part.where] = (level, part.text)
    
    def _print_paragraph(self, block, level=None, root=False, first=False):
        if isinstance(block, Code):
            return self._print_code(block)
        if isinstance(block, Table):
            return self._print_table(block)
        
        style = self._styles['default']
        if isinstance(block, Header):
            style = self._styles['h{0}'.format(block.size)]
        elif isinstance(block, BlockQuote):
            style = self._styles['blockquote']
        elif root:
            style = self._styles['root']
        
        if level:
            style = ParagraphStyle('style{0}'.format(id(block)),
                                   parent=style, bulletIndent=(level * 5))
        
        # Generate paragraph's text
        paragraphs, out = self._start_block(block, True)
        
        # Generate pseudo-anchor for first paragraph in page
        if first:
            out.write('<a name="{0}" />'.format(self._current_page.page_path.replace('/', '_')))
        
        for part in block.parts:
            if isinstance(part, Block) and not isinstance(part, Span):
                paragraphs, out = self._end_block(paragraphs, out, block, style)
                
                # Allow to use "root" style for root lists,  but forbid it in tables and incuts, etc.
                childroot = False
                if isinstance(part, ListEntry) or isinstance(part, ListBlock):
                    level = getattr(part, 'level', None)
                    childroot = root
                
                paragraphs.extend(self._print_paragraph(part, level, root=childroot))
                continue
            
            if isinstance(part, Image):
                # Create separate paragraph for large images
                img = self._print_image(part)
                
                if (img._width > self.MAX_INLINE_IMAGE_SIZE or 
                        img._height > self.MAX_INLINE_IMAGE_SIZE):
                    paragraphs, out = self._end_block(paragraphs, out, block, style)
                    paragraphs.append(img)
                    continue
            
            self._part_to_strio(part, out)
        
        paragraphs, _ = self._end_block(paragraphs, out, block, style, True)
        
        if root and isinstance(block, Incut):
            return [KeepTogether(paragraphs)]
        
        return paragraphs
    
    def _print_image(self, img):
        path = os.path.join(self.IMAGE_PATH, img.where)
        
        # We need to perform proportional resizing of images if they exceed 
        # page size and also apply dpi to them. So pre-read images.
        
        # TODO: use svg?
        
        image = PIL.Image.open(path)
        
        maxwidth, maxheight = self.PAGE_WIDTH * 0.8, self.PAGE_HEIGHT * 0.8
        imgwidth, imgheight = image.size
        
        imgwidth *= (pagesizes.inch / self.IMAGE_DPI)
        imgheight *= (pagesizes.inch / self.IMAGE_DPI)
        
        if imgwidth > maxwidth:
            imgheight /= (imgwidth / maxwidth)
            imgwidth = maxwidth
        if imgheight > maxheight:
            imgwidth /= (imgheight / maxheight)
            imgheight = maxheight
        
        return RLImage(path, width=imgwidth, height=imgheight)
    
    def _start_block(self, block, first=False):
        paragraphs = []
        out = cStringIO.StringIO()
        
        if isinstance(block, ListEntry):
            out.write('<bullet>&bull;</bullet>')
        
        if first:
            if isinstance(block, Header):
                paragraphs.append(CondPageBreak(pagesizes.inch))
            
            self._begin_incut(block, paragraphs)
        
        return paragraphs, out
        
    def _end_block(self, paragraphs, out, block, style, last=False):
        paragraphs.append(Paragraph(out.getvalue(), style))        
        _, out = self._start_block(block)
        
        if last:
            self._end_incut(block, paragraphs)
        
        return paragraphs, out
    
    def _begin_incut(self, block, paragraphs):
        incut_style, incut_message = self._incut_format(block)
        if incut_style:
            paragraphs.append(CondPageBreak(pagesizes.inch / 2))
            paragraphs.append(Paragraph(incut_message, style=incut_style))
    
    def _end_incut(self, block, paragraphs):
        incut_style, _ = self._incut_format(block)
        if incut_style:
            incut_style = ParagraphStyle(incut_style.name + '-end', parent=incut_style, 
                                         fontSize=4, leading=4)
            paragraphs.append(Paragraph('&nbsp;', style=incut_style))
    
    def _incut_format(self, block):
        if isinstance(block, CodeListing):
            return self._styles['codelisting'], 'Script file {0}'.format(block.fname)
        
        if not isinstance(block, Incut):
            return None, None
        
        style = self._styles['incut-{0}'.format(block.style)]
        message = self.INCUT_CLASSES[block.style]
        
        return style, message
    
    def _part_to_strio(self, part, out):
        tag = None
        tag_attrs = {}
        
        if isinstance(part, ItalicText):
            tag = 'i'
        elif isinstance(part, BoldText):
            tag = 'b'
        elif isinstance(part, Span):
            tag = 'b'
        elif isinstance(part, InlineCode):                    
            tag = 'font'
            tag_attrs['face'] = 'courier'
        elif isinstance(part, Reference):
            if not part.text:
                return
            
            ref_name = '{0}/{1}'.format(self._current_page.page_path, part.text)
            
            tag = 'a'
            tag_attrs['name'] = ref_name.replace('/', '_')
            part.text = ''
        elif isinstance(part, Image):
            # XXX: very dependent on book's directory structure
            path = os.path.join(self.IMAGE_PATH, part.where)
            out.write('<img src="{0}" height="14" width="14" />'.format(path))
            return
        elif isinstance(part, Link):
            tag_attrs['color'] = 'blue'
            
            # Generate name for page/anchor in page for internal links
            if part.type == Link.INTERNAL:
                tag = 'a'
                if '#' in part.where:
                    page_path, name = part.where.split('#')
                    tag_attrs['href'] = '#{0}/{1}'.format(page_path, name).replace('/', '_')
                else:
                    tag_attrs['href'] = '#{0}'.format(part.where).replace('/', '_')
                
            elif part.type == Link.EXTERNAL:
                tag = 'a'
                tag_attrs['href'] = part.where
        elif isinstance(part, BreakLine):
            out.write('<br />')
            return
        
        if tag:
            out.write('<{0}'.format(tag))
            
            for aname, avalue in tag_attrs.items():
                out.write(' {0}="{1}"'.format(aname, avalue))
            
            out.write('>')
            out.write(str(part))
            out.write('</{0}>'.format(tag))
        else:
            out.write(str(part))
                
    def _print_code(self, code):
        style = self._styles['code']
        
        if isinstance(code, CodeListing) and not self.print_sources:
            return [Paragraph(
                'Source file: <a href="{url}/{fname}">{fname}</a>'.format(
                    url=self.SOURCE_URL, fname=code.fname),
                style=style)]
        
        
        out = cStringIO.StringIO()
        for part in code.parts:
            for line in part.splitlines():
                self._print_code_line(line, out, style)
        
        paragraphs = []
        
        if isinstance(code, CodeListing):
            paragraphs = [_ListingInfoFlowable(code.fname)]
        
        self._begin_incut(code, paragraphs)
        paragraphs.append(Preformatted(out.getvalue(), style))
        self._end_incut(code, paragraphs)
        
        return paragraphs
    
    def _print_code_line(self, line, out, style):
        for old, new in self.CODE_REPLACE:
            line = line.replace(old, new)
            
        # split long lines
        width = stringWidth(line, style.fontName, style.fontSize)
        
        if width > self.MAX_CODE_LINE_WIDTH:
            for delimiter in ' ' + string.punctuation:
                try:
                    idx = line.rindex(delimiter, 0, self.MAX_CODE_LINE_LEN)
                    out.write(line[:idx+1])
                    
                    line = line[idx+1:]
                    
                    if any(c not in string.whitespace for c in line):
                        out.write(self.RIGHT_ARROW)
                        # TODO: Use line initial whitespace
                        out.write('\n        ')
                        
                    break
                except:
                    pass
        
        print >> out, line
    
    def _print_table(self, table):
        data = []  
        
        style = [('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                 ('VALIGN', (0, 0), (-1, -1), 'TOP'),]
        
        rowid = 0
        for row in table:
            colid = 0
            
            for cell in row:
                if not isinstance(cell, TableCell):
                    continue
                
                colmax, rowmax = colid, rowid
                
                if cell.colspan > 1 or cell.rowspan > 1:
                    colmax, rowmax = colid + cell.colspan - 1, rowid + cell.rowspan - 1
                    style.append(('SPAN', (colid, rowid), (colmax, rowmax)))
                    
                paragraphs = self._print_paragraph(cell)
                
                # Extend data with new table cell
                while len(data) <= rowmax:
                    data.append([])
                for currowid, row in enumerate(data):
                    while len(row) <= colmax:
                        row.append('')
                    if rowid == currowid:
                        row[colid] = paragraphs
                
                colid += 1
            
            if colid > 0:
                rowid += 1
        
        # TODO: allow to specify number of rows in table in md?
        
        return [RLTable(data, style=style, repeatRows=1)]