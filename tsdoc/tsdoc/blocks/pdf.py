import os
import sys

import re
import string

import itertools
import cStringIO

import PIL

from tempfile import NamedTemporaryFile
from PyPDF2 import PdfFileWriter, PdfFileReader, PdfFileMerger

from tsdoc.blocks import *

from reportlab.rl_config import defaultPageSize
from reportlab.platypus import (BaseDocTemplate, PageTemplate, NextPageTemplate,
                                PageBreak, Spacer, KeepTogether, Flowable, XPreformatted,
                                CondPageBreak, Frame)
from reportlab.platypus.tableofcontents import TableOfContents, SimpleIndex
from reportlab.platypus import Table as RLTable
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph as RLParagraph

from reportlab.pdfbase.pdfmetrics import (stringWidth, registerTypeFace, registerFontFamily,
                                          registerFont, EmbeddedType1Face, Font)
from reportlab.pdfbase.ttfonts import TTFont

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import enums, colors, pagesizes

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

    def scale(self, s):
        self.width *= s
        self.height *= s

class _ImageBlock(KeepTogether):
    def __init__(self, para, img):
        self.img = img
        KeepTogether.__init__(self, [para, img])
    
    def wrap(self, aW, aH):
        return KeepTogether.wrap(self, aW, aH)

class RLFlexibleParagraph(RLParagraph):
    BASE_WIDTH = 0.3 * pagesizes.inch
    
    def _calcFragWidth(self, frags):
        widths = []
        width = self.BASE_WIDTH
        
        for frag in frags:
            width += stringWidth(getattr(frag, 'text', ''), 
                                 frag.fontName, frag.fontSize)
            
            if hasattr(frag, 'lineBreak'):
                widths.append(width)
                width = self.BASE_WIDTH
        
        widths.append(width)
        return max(widths)
    
    def wrap(self, aW, aH):
        # Default implementation of RLParagraph eats all available width which is bad
        # for tables. We customize it so for small paragraphs, only minimal needed 
        # width will be used (based on paragraph frags)
        
        # We also need space width for "spaces" between paragraphs
        nW = self._calcFragWidth(self.frags)
        if self.bulletText:
            nW += self._calcFragWidth(self.frags)
        
        # Also account indentations
        style = self.style
        nW += max(style.leftIndent,
                  style.firstLineIndent) + style.rightIndent + style.bulletIndent
        
        aW = min(aW, nW)
        return RLParagraph.wrap(self, aW, aH)

class _FlowableIncut(Flowable):
    def __init__(self, coords, paragraphs):
        Flowable.__init__(self)
        self.coords = coords
        
        # Scale pdf images
        s = self.coords.get('s', 1.0)
        for para in paragraphs:
            if isinstance(para, _PDFImage):
                para.scale(s)
            
        self.paragraphs = paragraphs
        
        self._maxWidth = 0
    
    def wrap(self, w, h):
        self._maxWidth = self.coords.get('w', 1.0) * w
        return 0, 0
    
    def drawOn(self, canvas, x, y, _sW=None):
        W, H = canvas._pagesize
        x = max(x, self.coords.get('x', 0.0) * W)
        y -= self.coords.get('y', 0.0) * H
        
        canvas.saveState()
        canvas.translate(x, y)
        
        y = 0
        for para in self.paragraphs:
            w, h = para.wrap(self._maxWidth, H - y)
            para.drawOn(canvas, 0.0, y - h)
            y -= h
        
        canvas.restoreState()
    
class ListOfListings(TableOfContents):
    def __init__(self, ext):
        self.ext = re.compile(r'([^.]*)\.' + ext)
        return TableOfContents.__init__(self)
    
    def notify(self, kind, stuff):
        if kind == 'TOCListing':
            fname = stuff[1]
            if self.ext.match(fname):
                self.addEntry(*stuff)

class TSDocTemplate(BaseDocTemplate):
    DEFAULT_PAGE_TEMPLATE = 'Normal'
    INDEX_NAME = 'Index'
    
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
            
            # We do not need outline entries here because they are lost in a PyPDF2 mess --
            # instead cache outline entry here
            # self.canv.addOutlineEntry(header.strip(), key, level=level)
            self.outlines.append((self.page, level, header))
        
        if isinstance(flowable, SimpleIndex):
            self.notify('TOCEntry', (0, self.INDEX_NAME, self.page))
            self.outlines.append((self.page, 0, self.INDEX_NAME))
        
        if isinstance(flowable, _ListingInfoFlowable):
            self.notify('TOCListing', (1, flowable.fname, self.page))
        
    def handle_documentBegin(self):
        self.canv.setTitle(os.environ['TSDOC_HEADER'])
        self.canv.setAuthor(os.environ['TSDOC_AUTHOR'])
        
        self.header = ''
        self.outlines = []
        
        self._page_template = self.DEFAULT_PAGE_TEMPLATE
        self._handle_nextPageTemplate(self.DEFAULT_PAGE_TEMPLATE)
        
        return self._handle_documentBegin()
    
    def handle_nextPageTemplate(self, pt):
        self._page_template = pt
    
    def handle_pageEnd(self):
        if self.page < 3:
            return self._handle_pageEnd()
        
        canv = self.canv
        
        # Get main page frame boundaries
        frame = self.pageTemplate.frames[0]
        l, r = frame._leftPadding, frame._width - frame._rightPadding
        h = frame._bottomPadding
        
        # Draw line
        canv.saveState()
        canv.setStrokeColorRGB(0, 0, 0)
        canv.setLineWidth(0.5)
        canv.line(l, h, r, h)
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
        
        pw, ph = right.wrapOn(canv, (r - l), h)
        right.drawOn(canv, l, h - ph)
        
        pw, ph = left.wrapOn(canv, (r - l), h)
        left.drawOn(canv, l, h - ph)
        
        # Set next page template(-s)
        if self._page_template is not None:
            self._handle_nextPageTemplate(self._page_template)
        
        return self._handle_pageEnd()

class CheatSheetTemplate(TSDocTemplate):
    DEFAULT_PAGE_TEMPLATE = 'CheatSheet'
    
    def afterFlowable(self, flowable):
        if isinstance(flowable, RLParagraph):
            if flowable.style.name == 'h3':
                self.outlines.append((self.page, 0, flowable.text))
    
        if isinstance(flowable, _FlowableIncut):
            for para in flowable.paragraphs:
                self.afterFlowable(para)
        
    def handle_pageEnd(self):
        # Get main page frame boundaries
        frame = self.pageTemplate.frames[0]
        l, r = frame._leftPadding, frame._width - frame._rightPadding
        h = frame._topPadding
        H = frame._height
        
        # Draw heading
        para = RLParagraph(os.environ['TSDOC_HEADER'], 
                           style=ParagraphStyle('title', alignment=enums.TA_RIGHT, 
                                                fontName='LCMSS8', fontSize=12, leading=14))
        pw, ph = para.wrapOn(self.canv, (r - l), h)
        para.drawOn(self.canv, l, H - h)
        
        # Draw watermark
        with open('book/watermark.txt') as f:
            watermark = f.read()
        
        para = RLParagraph(watermark, 
                           style=ParagraphStyle('footer-base', fontName='Times-Roman', 
                                                leading=10, fontSize=8, alignment=enums.TA_LEFT))
        pw, ph = para.wrapOn(self.canv, (r - l), h)
        para.drawOn(self.canv, l, h - ph)
        
        return self._handle_pageEnd()

class PDFPrinter(Printer):
    single_doc = True
    xref_pages = False
    stream_mode = 'wb'
    
    PAGE_WIDTH, PAGE_HEIGHT = defaultPageSize           
    
    IMAGE_DPI = 150
    IMAGE_PATH = os.environ.get('TSDOC_IMGDIR')
    MAX_INLINE_IMAGE_SIZE = 64
    
    TITLE_FONT = ('fonts/lcmss8.afm', 'fonts/lcmss8.pfb', 'LCMSS8')
    MONO_FONT = ('Mono{0}', 'fonts/DejaVuSansMono{0}.ttf')
    
    RIGHT_ARROW = u"\u2192".encode('utf-8')
    MAX_CODE_LINE_LEN = 80
    MAX_CODE_LINE_WIDTH = PAGE_WIDTH * 0.8
    
    INCUT_CLASSES = { 'DEF' : 'Definition',
                      'WARN' : 'Warning',
                      'INFO':  'Information',
                      'NOTE': 'Note',
                      'DANGER': 'DANGER!' }
    
    CODE_TAGS = {BoldText: ('<b>', '</b>'),
                 ItalicText: ('<i>', '</i>')}
    
    SOURCE_URL = 'https://raw.githubusercontent.com/myaut/dtrace-stap-book/master/'
    
    TABLE_PADDING = 0.2 * pagesizes.inch
    
    TITLE_INDEX = 'Index'
    TITLE_TOC = 'Table of contents'
    
    SOURCE_INDEXES = [('SystemTap example scripts', r'stp'),
                      ('DTrace example scripts', r'd$'),
                      ('Other source files', '(?!d|stp)')]
    
    PAGE_TEMPLATES = {
        'Normal': (PAGE_WIDTH, PAGE_HEIGHT, pagesizes.inch, pagesizes.inch),
        'CheatSheet': (PAGE_WIDTH, PAGE_HEIGHT, pagesizes.inch / 2, pagesizes.inch / 2)
        }
    
    def __init__(self, print_index=True, doc_cls=TSDocTemplate):
        # Dictionary page name -> header/level used for generating TOCs
        self._page_info = {}
        self._current_page = None
        self._pdf_images = []
        
        self._story = []
        self._story_stack = []
        
        self.doc_cls = doc_cls
                
        self.print_sources = not os.environ.get('TSDOC_NO_SOURCES')
        self.print_index = print_index
        
        self.author = os.environ.get('TSDOC_AUTHOR')
        
        self._create_styles()
        self._set_page_template(self.doc_cls.DEFAULT_PAGE_TEMPLATE)
    
    def _create_styles(self):
        default = ParagraphStyle(
                    'default',
                    fontName='Times-Roman',
                    fontSize=10,
                    leading=12,
                    leftIndent=0, rightIndent=0, firstLineIndent=0,
                    alignment=enums.TA_LEFT,
                    spaceBefore=4, spaceAfter=4,
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
                                fontName='LCMSS8', alignment=enums.TA_LEFT,
                                spaceBefore=12, spaceAfter=6)
        incut = ParagraphStyle('header', parent=default, 
                                alignment=enums.TA_CENTER, textColor=colors.white, 
                                fontName='LCMSS8', fontSize=10)
        code = ParagraphStyle('code', parent=default,
                                fontSize=10, fontName='Mono')
        
        self._styles = {
            'default': default,
            
            'title': ParagraphStyle('title', alignment=enums.TA_CENTER, 
                                    fontName='LCMSS8', fontSize=42, leading=48),
            'title-author': ParagraphStyle('title-author', alignment=enums.TA_CENTER, 
                                    fontName='LCMSS8', fontSize=24, leading=32),
            
            'root': ParagraphStyle('root', parent=default, 
                                   fontSize=12, leading=14, firstLineIndent=8,
                                   alignment=enums.TA_JUSTIFY, spaceBefore=4, spaceAfter=4),
            
            'h1': ParagraphStyle('h1', parent=header, fontSize=28, leading=32),
            'h2': ParagraphStyle('h2', parent=header, fontSize=24, leading=28),
            'h3': ParagraphStyle('h3', parent=header, fontSize=18, leading=22),
            'h4': ParagraphStyle('h4', parent=header, fontSize=16, leading=20),
            'h5': ParagraphStyle('h5', parent=header, fontSize=14, leading=16),
            'h6': ParagraphStyle('h6', parent=header, fontSize=12, leading=14),
            
            'code': code,
            'subcode': ParagraphStyle('subcode', parent=code, fontSize=8, leading=10),
            
            'incut-DEF': ParagraphStyle('incut-def', parent=incut, backColor=colors.darkgray),
            'codelisting': ParagraphStyle('codelisting', parent=incut, backColor=colors.darkgreen),
            'incut-INFO': ParagraphStyle('incut-info', parent=incut, backColor=colors.darkblue),
            'incut-NOTE': ParagraphStyle('incut-note', parent=incut, backColor=colors.darkslateblue),
            'incut-WARN': ParagraphStyle('incut-warn', parent=incut, backColor=colors.darkorange),
            'incut-DANGER': ParagraphStyle('incut-danger', parent=incut, backColor=colors.darkred),
            
            'blockquote': ParagraphStyle('blockquote', parent=default, leftIndent=20)
            }
    
    def _set_page_template(self, name):
        self._page_template_name = name
        self._page_template = self.PAGE_TEMPLATES[name]
    
    def _get_page_width(self):
        return (self._page_template[0] - 2*self._page_template[2]) 
    
    def do_print_pages(self, stream, header, pages):
        story = self._story
        self.stream = stream
        
        print >> sys.stderr, "Generating PDF..."
        
        self._register_fonts()
        
        pages = iter(pages)
        
        if self.print_index:
            index = next(pages)
            self._current_page = index
            self._print_index(index, header)
        
        for page in pages:
            # In the beginning of new section -- add page break
            self._current_page = page
            if hasattr(page, 'is_external'):
                story.append(PageBreak())
                story.append(Spacer(self._page_template[0],
                                    self._page_template[1] / 5))
            
            if self.print_index:
                story.append(_PageInfoFlowable(page, self._page_info.get(page.page_path)))            
            
            if hasattr(page, 'is_external'):
                story.append(RLParagraph(page.header,
                                         style=self._styles['h2']))
                continue
            
            # Render page blocks
            for block in page:
                self._print_paragraph(block, root=True)
                
            if self._page_template_name != self.doc_cls.DEFAULT_PAGE_TEMPLATE:
                # If page has overriden page styles, revert it afterwards
                story.append(NextPageTemplate(self.doc_cls.DEFAULT_PAGE_TEMPLATE))
                self._page_template_name = self.doc_cls.DEFAULT_PAGE_TEMPLATE
        
        # Rendering PDF...
        print >> sys.stderr, "Rendering PDF..."
        
        docf = NamedTemporaryFile()
        doc = self.doc_cls(docf)
        doc.addPageTemplates(self._get_page_templates())
        
        if self.print_index:
            canvasmaker = self._print_reference()
            doc.multiBuild(story, canvasmaker=canvasmaker)
        else:
            doc.build(story)
        
        # Rendering PDF with images...
        print >> sys.stderr, "Rendering PDF images..."
        
        docf.flush()
        
        self._merge_pdf_images(docf, stream, doc.outlines)
    
    def _merge_pdf_images(self, docf, stream, outlines):
        pdfin = PdfFileReader(docf.name)
        
        pdfout = PdfFileWriter()
        pdfout._info.getObject().update(pdfin.getDocumentInfo())
        
        # embed images into file
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
        
        # create outlines
        stack = []
        for pageno, level, header in outlines:
            stack = stack[:level]
            
            parent = (stack[0] if stack else None)
            stack.append(pdfout.addBookmark(header.strip(), pageno - 1, parent))
        
        pdfout.write(stream)
    
    def _register_fonts(self):
        afmfile, pfbfile, fontname = self.TITLE_FONT
        registerTypeFace(EmbeddedType1Face(afmfile, pfbfile))
        registerFont(Font(fontname, fontname, 'WinAnsiEncoding'))
        
        for suffix in ['', '-Bold', '-Oblique', '-BoldOblique']:
            registerFont(TTFont(self.MONO_FONT[0].format(suffix), 
                                self.MONO_FONT[1].format(suffix)))
        registerFontFamily('Mono', normal='Mono', bold='Mono-Bold', 
                           italic='Mono-Oblique', boldItalic='Mono-BoldOblique')
    
    def _get_page_templates(self):
        templates = []
        
        for (name, (w, h, xm, ym)) in self.PAGE_TEMPLATES.items():
            templates.append(PageTemplate(id=name, 
                                          frames=[Frame(0, 0, w, h, xm, ym, xm, ym, id=name)], 
                                          pagesize=(w, h)))
            
        return templates

    def _print_index(self, index, header):
        # Generate index page and TOC based on it 
        story = self._story
        story.append(Spacer(self._page_template[0], self._page_template[1] / 4))
        story.append(RLParagraph(header, self._styles['title']))
        story.append(Spacer(self._page_template[0], self._page_template[1] / 5))
        story.append(RLParagraph(self.author, self._styles['title-author']))
        
        blocks = iter(index)
        for block in blocks:
            refs = [part.text
                    for part in block 
                    if isinstance(part, Reference)]
            if '__endfrontpage__' in refs:
                story.append(PageBreak())
            if '__endbackpage__' in refs:
                break
            
            self._print_paragraph(block, root=True)
            
        self._find_page_info(blocks)
        
        # Print table of contents. index.md contains 
        story.append(PageBreak())
        story.append(RLParagraph(self.TITLE_TOC, self._styles['h3']))
        self._add_toc(TableOfContents())
        
        # Generate list of sources
        if self.print_sources:
            story.append(PageBreak())
            for title, re_ext in self.SOURCE_INDEXES:
                story.append(RLParagraph(title, self._styles['h3']))
                self._add_toc(ListOfListings(re_ext))
    
    def _print_reference(self):
        index = SimpleIndex()
        self._story.append(PageBreak())
        self._story.append(RLParagraph(self.TITLE_INDEX, self._styles['h3']))
        self._story.append(index)
        
        return index.getCanvasMaker()
    
    def _add_toc(self, toc):
        root = self._styles['root']
        
        toc.levelStyles = [
            ParagraphStyle('TOCHeading1', parent=root, 
                fontName='Times-Bold', fontSize=14,
                leftIndent=20, firstLineIndent=-20, spaceBefore=5, leading=16),
            ParagraphStyle('TOCHeading2', parent=root,
                leftIndent=40, firstLineIndent=-20, spaceBefore=0, leading=10),
            ParagraphStyle('TOCHeading3', parent=root,
                leftIndent=60, firstLineIndent=-20, spaceBefore=0, leading=10)
            ]
        
        self._story.append(toc)
    
    def _find_page_info(self, parts, level=1):
        for part in parts:
            if isinstance(part, ListEntry):
                level = part.level
                
            if isinstance(part, Block):
                self._find_page_info(part.parts, level)
                
            if isinstance(part, Link) and part.type == Link.INTERNAL:
                self._page_info[part.where] = (level, part.text)
    
    def _save_state(self):        
        self._story_stack.append(self._story)
        self._story = []
    
    def _restore_state(self):
        story = self._story
        self._story = self._story_stack.pop()
        return story
    
    def _print_paragraph(self, block, level=None, root=False, width=1.0):
        if isinstance(block, Code):
            return self._print_code(block, root)
        if isinstance(block, Table):
            return self._print_table(block, table_width=width)
        if isinstance(block, PageSpacer):
            if block.isbreak:
                if block.iscond:
                    return self._story.append(CondPageBreak(block.height * self._page_template[1]))
                return self._story.append(PageBreak())
            if block.style:
                self._set_page_template(block.style)
                # Break to a new page unless we already have whole page available. This trick
                # is used to render cheatsheets both in book and in separate PDF without extra page
                return self._story.append(NextPageTemplate(block.style))
            return self._story.append(Spacer(0, block.height * self._page_template[1]))
        
        # Save state to get paragraphs
        if isinstance(block, FlowableIncut):
            width = block.coords.get('w', width)
            self._save_state()
        elif root and isinstance(block, Incut):
            self._save_state()
        
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
        out = self._start_block(block, True)
        
        for part in block.parts:
            if isinstance(part, Block) and not isinstance(part, Span):
                out = self._end_block(root, out, block, style)
                
                # Allow to use "root" style for root lists,  but forbid it in tables and incuts, etc.
                childroot = False
                if isinstance(part, ListEntry) or isinstance(part, ListBlock):
                    level = getattr(part, 'level', None)
                    childroot = root
                if isinstance(part, Code) or isinstance(part, Table):
                    childroot = root
                
                self._print_paragraph(part, level, root=childroot, width=width)
                continue
            
            if isinstance(part, Image):
                # Create separate paragraph for large images
                img = self._print_image(part, width)
                
                if not isinstance(img, RLImage) or (
                        img._width > self.MAX_INLINE_IMAGE_SIZE or 
                        img._height > self.MAX_INLINE_IMAGE_SIZE):
                    out = self._end_block(root, out, block, style)
                    
                    # We want to keep image together with a paragraph before
                    if self._story:
                        img = _ImageBlock(self._story.pop(), img)
                        
                    self._story.append(img)
                    continue
            
            self._part_to_strio(part, out, style.fontSize)
        
        self._end_block(root, out, block, style, True)
        
        if isinstance(block, FlowableIncut):
            incut = _FlowableIncut(block.coords, self._restore_state())
            return self._story.append(incut)
        if root and isinstance(block, Incut):
            incut = KeepTogether(self._restore_state())
            return self._story.append(incut)
    
    def _print_image(self, img, width):
        path = os.path.join(self.IMAGE_PATH, img.where)
        
        # We need to perform proportional resizing of images if they exceed 
        # page size and also apply dpi to them. So pre-read images.
        
        image = PIL.Image.open(path)
        
        maxwidth, maxheight = self._get_page_width() * width, self._page_template[1]
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
        out = cStringIO.StringIO()
        
        if isinstance(block, ListEntry):
            out.write('<bullet>&bull;</bullet>')
        
        if first:
            if isinstance(block, Header):
                self._story.append(CondPageBreak((7 - block.size) * pagesizes.inch / 2))
            
            self._begin_incut(block)
        
        return out
        
    def _end_block(self, root, out, block, style, last=False):
        if any(c not in string.whitespace
               for c in out.getvalue()):
            self._story.append((RLParagraph if root else RLFlexibleParagraph)(out.getvalue(), style))        
        out = self._start_block(block)
        
        if last:
            self._end_incut(block)
        
        return out
    
    def _begin_incut(self, block):
        incut_style, incut_message = self._incut_format(block)
        if incut_style:
            self._story.append(CondPageBreak(pagesizes.inch / 2))
            self._story.append(RLParagraph(incut_message, style=incut_style))
    
    def _end_incut(self, block):
        incut_style, _ = self._incut_format(block)
        if incut_style:
            incut_style = ParagraphStyle(incut_style.name + '-end', parent=incut_style, 
                                         fontSize=4, leading=4)
            self._story.append(RLParagraph('&nbsp;', style=incut_style))
    
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
                
    def _print_code(self, code, root=False):
        style = self._styles['code' if root else 'subcode']
        
        if isinstance(code, CodeListing) and not self.print_sources:
            self._story.append(RLParagraph(
                'Source file: <a href="{url}/{fname}" color="blue">{fname}</a>'.format(
                    url=self.SOURCE_URL, fname=code.fname),
                style=self._styles['default']))
            return
        
        
        out = cStringIO.StringIO()
        for part in code.parts:
            # TODO: support bold/italic text in preformatted
            text = str(part).replace('\t', '    ')
            
            for line in text.splitlines(True):
                tags = self.CODE_TAGS.get(type(part), ('', ''))
                self._print_code_line(line, out, style, tags)
        
        if isinstance(code, CodeListing):
            self._story.append(_ListingInfoFlowable(code.fname))
        
        self._begin_incut(code)
        self._story.append(XPreformatted(out.getvalue(), style))
        self._end_incut(code)
    
    def _print_code_line(self, line, out, style, tags):
        out.write(tags[0]) 
        
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
        
        out.write(line)
        out.write(tags[1]) 
    
    def _print_table(self, table, table_width=1.0):       
        parastyle = self._styles['default']
        data = []  
        
        style = [('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
                 ('VALIGN', (0, 0), (-1, -1), 'TOP'),]
        
        rowid = 0
        for row in table:
            if not isinstance(row, TableRow):
                continue
            
            datarow = []
            colid = 0
            
            for cell in row:
                if not isinstance(cell, TableCell):
                    continue
                
                # Fill colspans and rowspans with empty cells
                for cmd in style:
                    if (cmd[0] == 'SPAN' and 
                            cmd[2][0] <= colid <= cmd[1][0] and
                            cmd[1][1] <= rowid <= cmd[2][1]):
                        colspan = cmd[2][0] - colid + 1
                        datarow.extend([[]] * colspan)
                        colid += colspan
                
                if cell.colspan > 1 or cell.rowspan > 1:
                    colmax, rowmax = colid + cell.colspan - 1, rowid + cell.rowspan - 1
                    style.append(('SPAN', (colid, rowid), (colmax, rowmax)))
                
                self._save_state()
                self._print_paragraph(cell)
                datarow.append(self._restore_state())
                colid += 1
                            
            if colid > 0:
                data.append(datarow)
                rowid += 1
                
        # TODO: allow to specify number of rows in table in md?
        if not data:
            return
        
        table_width *= self._get_page_width()
        if table.colwidths:
            col_widths = [width * table_width
                          for width in table.colwidths]
        else:
            col_widths = self._compute_col_widths(data, table_width)
        
        self._story.append(RLTable(data, style=style, repeatRows=1, colWidths=col_widths))
    
    def _compute_col_widths(self, data, table_width):
        # Find maximum length of paragraph in table to determine better col width 
        colcount = max(len(datarow) for datarow in data)
        
        col_widths = [self.TABLE_PADDING] * colcount
        col_heights = [self.TABLE_PADDING] * colcount
        min_col_widths = [self.TABLE_PADDING] * colcount
        
        for row in data:
            for colid, col in enumerate(row):
                for para in col:
                    width, height = para.wrap(table_width, self._page_template[1])
                    col_widths[colid] = max(width, col_widths[colid])
                    col_heights[colid] += height
                    
                    min_width = (para.minWidth() if isinstance(para, RLParagraph)
                                 else getattr(para, 'width', 0))
                    min_col_widths[colid] = max(min_width, min_col_widths[colid])
        
        # Normalize column widths
        total_width = sum(col_widths)
        max_height = max(col_heights)
        col_widths = [min(width * height * table_width / total_width / max_height, 
                          min_width) + self.TABLE_PADDING
                      for width, height, min_width 
                      in zip(col_widths, col_heights, min_col_widths)]
        
        # Compensate for extra width due to min column width
        extra_width = sum(col_widths) - table_width
        col_widths = [width - (extra_width / len(col_widths))
                      for width in col_widths]
        
        return col_widths