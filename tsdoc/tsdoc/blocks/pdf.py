import os
import sys

import re
import string

import itertools
import cStringIO

import PIL

from tempfile import NamedTemporaryFile
from PyPDF2 import PdfFileWriter, PdfFileReader

from tsdoc.blocks import *

from reportlab.rl_config import defaultPageSize
from reportlab.platypus import (Paragraph, Preformatted, SimpleDocTemplate, 
                                PageBreak, Spacer, KeepTogether, Flowable, 
                                CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents, SimpleIndex
from reportlab.platypus import Table as RLTable
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph as RLParagraph

from reportlab.pdfbase.pdfmetrics import (stringWidth, registerTypeFace, 
                                          registerFont, EmbeddedType1Face, Font)
from reportlab.pdfbase.ttfonts import TTFont

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import enums, colors, pagesizes

from tsdoc.svg2rlg import svg2rlg

class _InfoFlowable(Flowable):
    # Hidden flowable for information 
    def __init__(self):
        self.width = 0
        self.height = 0
    
    def draw(self):
        pass

class _PageInfoFlowable(_InfoFlowable):
    # This flowable incapsulates TSDoc pages. It is not shown on canvas
    # but used for generating table of contents
    def __init__(self, page, info):
        self.info = info
        self.page = page
        _InfoFlowable.__init__(self)

class _ListingInfoFlowable(_InfoFlowable):
    def __init__(self, fname):
        self.fname = fname
        _InfoFlowable.__init__(self)
    
    def draw(self):
        pass

class _PDFImage(Flowable):
    def __init__(self, fname, width, height):
        Flowable.__init__(self)
        self.fname = fname
        self.width = width 
        self.height = height
        self.x = 0
        self.y = 0
        self.page = 0
        
    def drawOn(self, canvas, x, y, _sW=None):
        # Do not draw PDFImage, just save position -- it is actually drawn later with PyPDF
        self.x = x + canvas._currentMatrix[-2]
        self.y = y + canvas._currentMatrix[-1]
        self.page = canvas.getPageNumber()
    
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
            key = flowable.page.page_path.replace('/', '_')
            
            if flowable.info:
                level, header = flowable.info
            else:
                header = flowable.page.header
                level = 1
                
                if hasattr(flowable.page, 'is_external'):
                    level = 0
                    self.header = header
                
            self.notify('TOCEntry', (level, header, self.page))
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(header.strip(), key, level=level)
        
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
        right = RLParagraph(rtext, 
                            style=ParagraphStyle('footer-right', 
                                    parent=style, alignment=enums.TA_RIGHT))
        left = RLParagraph(ltext,
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
    stream_mode = 'wb'
    
    PAGE_WIDTH, PAGE_HEIGHT = defaultPageSize           
    
    IMAGE_DPI = 120
    IMAGE_PATH = 'build/images'
    MAX_INLINE_IMAGE_SIZE = 64
    
    TITLE_FONT = ('tsdoc/lcmss8.afm', 'tsdoc/lcmss8.pfb', 'LCMSS8')
    MONO_FONT = 'tsdoc/DejaVuSansMono.ttf'
    
    RIGHT_ARROW = u"\u2192".encode('utf-8')
    MAX_CODE_LINE_LEN = 80
    MAX_CODE_LINE_WIDTH = PAGE_WIDTH * 0.8
    
    INCUT_CLASSES = { 'DEF' : 'Definition',
                      'WARN' : 'Warning',
                      'INFO':  'Information',
                      'NOTE': 'Note',
                      'DANGER': 'DANGER!' }
    
    SOURCE_URL = 'https://raw.githubusercontent.com/myaut/dtrace-stap-book/master/'
    
    TABLE_WIDTH = PAGE_WIDTH * 0.75
    TABLE_MIN_COL_WIDTH = 2 * pagesizes.inch
    
    TITLE_INDEX = 'Index'
    TITLE_TOC = 'Table of contents'
    
    SOURCE_INDEXES = [('SystemTap example scripts', r'stp'),
                      ('DTrace example scripts', r'd$'),
                      ('Other source files', '(?!d|stp)')]
    
    def __init__(self):
        # Dictionary page name -> header/level used for generating TOCs
        self._page_info = {}
        self._current_page = None
        self._pdf_images = []
        
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
                                fontName='LCMSS8', alignment=enums.TA_LEFT)
        incut = ParagraphStyle('header', parent=default, 
                                alignment=enums.TA_CENTER, textColor=colors.white, 
                                fontName='LCMSS8', fontSize=10)
        
        self._styles = {
            'default': default,
            
            'title': ParagraphStyle('title', alignment=enums.TA_CENTER, 
                                    fontName='LCMSS8', fontSize=42, leading=48),
            
            'root': ParagraphStyle('root', parent=default, 
                                   fontSize=12, leading=14, firstLineIndent=8,
                                   alignment=enums.TA_JUSTIFY, spaceBefore=4, spaceAfter=4),
            
            'h1': ParagraphStyle('h1', parent=header, fontSize=28, leading=32),
            'h2': ParagraphStyle('h2', parent=header, fontSize=24, leading=28),
            'h3': ParagraphStyle('h3', parent=header, fontSize=18, leading=22),
            'h4': ParagraphStyle('h4', parent=header, fontSize=16, leading=20),
            'h5': ParagraphStyle('h5', parent=header, fontSize=14, leading=16),
            'h6': ParagraphStyle('h6', parent=header, fontSize=12, leading=14),
            
            'code': ParagraphStyle('code', parent=default,
                                   fontSize=10, fontName='Mono',
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
        
        print >> sys.stderr, "Generating PDF..."
        
        self._register_fonts()
        
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
                paragraphs.append(RLParagraph(page.header,
                                              style=self._styles['h2']))
                continue
            
            # Render page blocks
            for block in page:
                paragraphs.extend(self._print_paragraph(block, root=True))
        
        index = SimpleIndex()
        paragraphs.append(PageBreak())
        paragraphs.append(RLParagraph(self.TITLE_INDEX, self._styles['h3']))
        paragraphs.append(index)
        
        print >> sys.stderr, "Rendering PDF..."
        
        docf = NamedTemporaryFile()
        doc = _TSDocTemplate(docf)
        doc.multiBuild(paragraphs, canvasmaker=index.getCanvasMaker())
        
        print >> sys.stderr, "Rendering PDF images..."
        
        docf.flush()
        pdfin = PdfFileReader(docf.name)
        pdfout = PdfFileWriter()
        for pageno, page in enumerate(pdfin.pages):
            for img in self._pdf_images:
                if img.page != (pageno + 1):
                    continue
                
                # Load image
                imgin = PdfFileReader(img.fname)
                imgpage = imgin.getPage(0)
                scale = min(img.width / imgpage.mediaBox[2].as_numeric(), 
                            img.height / imgpage.mediaBox[3].as_numeric())
                page.mergeScaledTranslatedPage(imgpage, scale, img.x, img.y)
            
            pdfout.addPage(page)
        
        pdfout.write(stream)
    
    def _register_fonts(self):
        afmfile, pfbfile, fontname = self.TITLE_FONT
        registerTypeFace(EmbeddedType1Face(afmfile, pfbfile))
        registerFont(Font(fontname, fontname, 'WinAnsiEncoding'))
        
        registerFont(TTFont('Mono', self.MONO_FONT))
    
    def _print_index(self, paragraphs, index, header):
        # Generate index page and TOC based on it 
        paragraphs.append(Spacer(self.PAGE_WIDTH, self.PAGE_HEIGHT / 4))
        paragraphs.append(RLParagraph(header, self._styles['title']))
        paragraphs.append(Spacer(self.PAGE_WIDTH, self.PAGE_HEIGHT / 5))
        
        blocks = iter(index)
        for block in blocks:
            if any(isinstance(part, Reference) and part.text == '__endfrontpage__'
                   for part in block):
                break
            paragraphs.extend(self._print_paragraph(block, root=True))
            
        self._find_page_info(blocks)
        
        # Print table of contents. index.md contains 
        paragraphs.append(PageBreak())
        paragraphs.append(RLParagraph(self.TITLE_TOC, self._styles['h3']))
        self._add_toc(paragraphs, TableOfContents())
        
        # Generate list of sources
        if self.print_sources:
            paragraphs.append(PageBreak())
            for title, re_ext in self.SOURCE_INDEXES:
                paragraphs.append(RLParagraph(title, self._styles['h3']))
                self._add_toc(paragraphs, ListOfListings(re_ext))
    
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
                level = part.level
                
            if isinstance(part, Block):
                self._find_page_info(part.parts, level)
                
            if isinstance(part, Link) and part.type == Link.INTERNAL:
                self._page_info[part.where] = (level, part.text)
    
    def _print_paragraph(self, block, level=None, root=False):
        if isinstance(block, Code):
            return self._print_code(block)
        if isinstance(block, Table):
            return self._print_table(block)
        
        # Pick paragraph style based on block nature
        style = self._styles['default']
        if isinstance(block, Header):
            style = self._styles['h{0}'.format(block.size)]
        elif isinstance(block, BlockQuote):
            style = self._styles['blockquote']
        elif root:
            style = self._styles['root']
        
        # Generate style for lists on-the-fly
        if level:
            style = ParagraphStyle('style{0}'.format(id(block)),
                                   parent=style, bulletIndent=(level * 10),
                                   spaceAfter=0, spaceBefore=0)
        
        # Generate paragraph's text. PLATYPUS doesn't support hiearchial paragraphs like HTML do,
        # so we linearize blocks into paragraphs list: each time subblock appear, we complete 
        # current paragraph and start a new one. 
        
        # For Incuts which may have subparagraphs, we add two colored paragraphs before and after 
        # so they will be distinguishable. Span is another exception -- it doesn't rendered as 
        # separate paragraph, but as a <span> within paragraph.
        paragraphs, out = self._start_block(block, True)
        
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
                
                if not isinstance(img, RLImage) or (
                        img._width > self.MAX_INLINE_IMAGE_SIZE or 
                        img._height > self.MAX_INLINE_IMAGE_SIZE):
                    paragraphs, out = self._end_block(paragraphs, out, block, style)
                    paragraphs.append(img)
                    continue
            
            self._part_to_strio(part, out, style.fontSize)
        
        paragraphs, _ = self._end_block(paragraphs, out, block, style, True)
        
        if root and isinstance(block, Incut):
            return [KeepTogether(paragraphs)]
        
        return paragraphs
    
    def _print_image(self, img):
        path = os.path.join(self.IMAGE_PATH, img.where)
        
        # We need to perform proportional resizing of images if they exceed 
        # page size and also apply dpi to them. So pre-read images.
        
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
        
        if imgwidth > self.MAX_INLINE_IMAGE_SIZE or imgheight > self.MAX_INLINE_IMAGE_SIZE:
            # Try to use pdf images for large images so it will be vectorized
            pdfpath = path.replace('.png', '.pdf')
            if os.path.exists(pdfpath):
                pdfimg = _PDFImage(pdfpath, imgwidth, imgheight)
                self._pdf_images.append(pdfimg)
                return pdfimg
        
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
        paragraphs.append(RLParagraph(out.getvalue(), style))        
        _, out = self._start_block(block)
        
        if last:
            self._end_incut(block, paragraphs)
        
        return paragraphs, out
    
    def _begin_incut(self, block, paragraphs):
        incut_style, incut_message = self._incut_format(block)
        if incut_style:
            paragraphs.append(CondPageBreak(pagesizes.inch / 2))
            paragraphs.append(RLParagraph(incut_message, style=incut_style))
    
    def _end_incut(self, block, paragraphs):
        incut_style, _ = self._incut_format(block)
        if incut_style:
            incut_style = ParagraphStyle(incut_style.name + '-end', parent=incut_style, 
                                         fontSize=4, leading=4)
            paragraphs.append(RLParagraph('&nbsp;', style=incut_style))
    
    def _incut_format(self, block):
        if isinstance(block, CodeListing):
            return self._styles['codelisting'], 'Script file {0}'.format(block.fname)
        
        if not isinstance(block, Incut):
            return None, None
        
        style = self._styles['incut-{0}'.format(block.style)]
        message = self.INCUT_CLASSES[block.style]
        
        return style, message
    
    def _part_to_strio(self, part, out, font_size):
        tag = None
        tag_attrs = {}
        text = str(part)
        
        if isinstance(part, ItalicText):
            tag = 'i'
        elif isinstance(part, BoldText):
            tag = 'b'
        elif isinstance(part, Span):
            if part.style == 'small':
                font_size -= 2
                out.write('<font size={0}>'.format(font_size))
            elif part.style[0] == '#':
                out.write('<font color="{0}">'.format(part.style[1:]))
                
            for part in part.parts:
                self._part_to_strio(part, out, font_size)
            out.write('</font>')
            return
        elif isinstance(part, InlineCode):
            # DejaVu Sans Mono appears to look larger than Times, so we correct its size
            # for inline code
            tag = 'font'
            tag_attrs['face'] = 'Mono'
            tag_attrs['size'] = str(font_size - 2)
        elif isinstance(part, Reference):
            if not part.text:
                return
            
            text = ''
            reftag, refvalue = part.parse()
            
            if reftag == '__index__':
                tag = 'index'
                tag_attrs['item'] = refvalue
            else:
                ref_name = '{0}/{1}'.format(self._current_page.page_path, part.text)
                
                tag = 'a'
                tag_attrs['name'] = ref_name.replace('/', '_')
        elif isinstance(part, Image):
            path = os.path.join(self.IMAGE_PATH, part.where)
            
            text = ''
            tag = 'img'
            tag_attrs['src'] = path
            tag_attrs['height'] = tag_attrs['width'] = '14'
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
            tag = 'br'
            text = ''
        
        if not tag:
            out.write(text)
            return
        
        out.write('<{0}'.format(tag))
        
        for aname, avalue in tag_attrs.items():
            out.write(' {0}="{1}"'.format(aname, avalue))
        
        if text:
            out.write('>')
            out.write(text)
            out.write('</{0}>'.format(tag))
        else:
            out.write(' />')
                
    def _print_code(self, code):
        style = self._styles['code']
        
        if isinstance(code, CodeListing) and not self.print_sources:
            return [RLParagraph(
                'Source file: <a href="{url}/{fname}">{fname}</a>'.format(
                    url=self.SOURCE_URL, fname=code.fname),
                style=style)]
        
        
        out = cStringIO.StringIO()
        for part in code.parts:
            # TODO: support bold/italic text in preformatted
            text = str(part).replace('\t', '    ')
            
            for line in text.splitlines():
                self._print_code_line(line, out, style)
        
        paragraphs = []
        
        if isinstance(code, CodeListing):
            paragraphs = [_ListingInfoFlowable(code.fname)]
        
        self._begin_incut(code, paragraphs)
        paragraphs.append(Preformatted(out.getvalue(), style))
        self._end_incut(code, paragraphs)
        
        return paragraphs
    
    def _print_code_line(self, line, out, style):    
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
        parastyle = self._styles['default']
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
        
        if not data:
            return []
        
        # Find maximum length of paragraph in table to determine better col width 
        # TODO: better to use wrapon?
        col_widths = [max(stringWidth(para.text, fontName=parastyle.fontName, fontSize=parastyle.fontSize) 
                          for para 
                          in itertools.chain(*[row[colid] 
                                               for row in data
                                               if len(row) > colid])
                          if isinstance(para, RLParagraph))
                      for colid in range(len(data[0]))]
        total_width = sum(col_widths)
        
        # Normalize column widths
        col_widths = [min(width * self.TABLE_WIDTH / total_width, 
                          self.TABLE_MIN_COL_WIDTH)
                      for width in col_widths]
        
        # Compensate for extra width due to min column width
        extra_width = sum(col_widths) - self.TABLE_WIDTH
        col_widths = [width - (extra_width / len(col_widths))
                      for width in col_widths]
            
        return [RLTable(data, style=style, repeatRows=1, colWidths=col_widths)]
