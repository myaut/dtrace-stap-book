import os
import sys
import datetime

from tsdoc.blocks import *

import zipfile
from zipfile import ZipFile
from tempfile import NamedTemporaryFile

from xml.etree import ElementTree as etree

class _ZipStream(object):
    def __init__(self, zipf, fname):
        self.zipf = zipf
        self.fname = fname
        
        self.tmpf = NamedTemporaryFile()
    
    def __del__(self):
        self.tmpf.flush()
        self.zipf.write(self.tmpf.name, self.fname)
    
    def __getattr__(self, attrib):
        return getattr(self.tmpf, attrib)

class EpubPrinter(Printer):
    single_doc = True
    xref_pages = False
    
    NAMESPACES = {'XML': 'http://www.w3.org/XML/1998/namespace',
                  'EPUB': 'http://www.idpf.org/2007/ops',
                  'DAISY': 'http://www.daisy.org/z3986/2005/ncx/',
                  'OPF': 'http://www.idpf.org/2007/opf',
                  'CONTAINERNS': 'urn:oasis:names:tc:opendocument:xmlns:container',
                  'DC': "http://purl.org/dc/elements/1.1/",
                  'XHTML': 'http://www.w3.org/1999/xhtml'}
    
    CONTAINER_PATH = 'META-INF/container.xml'

    CONTAINER_XML = '''<?xml version='1.0' encoding='utf-8'?>
    <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
    <rootfiles>
        <rootfile media-type="application/oebps-package+xml" full-path="{folder_name}/content.opf"/>
    </rootfiles>
    </container>
    '''
    
    XML_HEADER = '<?xml version="1.0" encoding="utf-8"?>'
    HTML_HEADER = '<!DOCTYPE html>'
    
    FOLDER_NAME = 'EPUB'
    IDENTIFIER_ID = 'pub-identifier'
    
    SOURCE_URL = 'https://raw.githubusercontent.com/myaut/dtrace-stap-book/master/'
    
    IMAGE_PATH = 'build/images'
    CSS_PATH = 'book/epub.css'
    
    INCUT_CLASSES = { 'DEF' : 'Definition',
                      'WARN' : 'Warning',
                      'INFO':  'Information',
                      'NOTE': 'Note',
                      'DANGER': 'DANGER!' }
    
    def __init__(self):
        self._epub = None
        
        self._page_name = None
        self._anchor_prefix = None
        self._page_stream = None
        self._page_root = None
        self._page_body = None
        self._page_div = None
        
        self._docspaces = []
        self._ncx_stream = None
        self._ncx_root = None
        self._toc_stream = None
        self._toc_root = None
        self._toc_state = None
        
        self._page_info = {}
        
        self.print_sources = not os.environ.get('TSDOC_NO_SOURCES')
        
        self.uid = os.environ.get('TSDOC_UID')
        self.title = os.environ.get('TSDOC_HEADER')
        self._metadata = [('DC', 'identifier', self.uid),
                          ('DC', 'title', self.title),
                          ('DC', 'creator', os.environ.get('TSDOC_AUTHOR')),
                          ('DC', 'language', 'en')]
        
        self._items = []
        self._images = set()
        
    def do_print_pages(self, stream, header, pages):
        ''' Generates EPUB. EPUB is a zip file with bunch of XMLs/XHTMLs.
        
            List of files within EPUB is tracked via self._items. Order of creating items 
            is crucial for "spine" items as they appear in order they were created in book.
            
            HTMLs are added in this order:
                - Cover cover.html
                - TOC toc01.html
                For each DocSpaceIndex page:
                    - Chapter chXX.html created
                    
            Each XML is HTML is wrapped as _ZipStream object which is temporary file which is
            is zipped and deleted on deletion. We also keep root tag to render XML to it.
            
            When rendering is complete, OPF file is generated.'''
        self._epub = ZipFile(stream, 'w', zipfile.ZIP_DEFLATED)
        self._epub.writestr('mimetype', 'application/epub+zip', 
                            compress_type=zipfile.ZIP_STORED)
        
        self._ncx_stream = self._create_item('toc.ncx', 'toc.ncx', 
                                             "application/x-dtbncx+xml", unique=True)
        
        self._add_css()
        
        pages = iter(pages)
        index = next(pages)
        self._write_cover(index, header)
        
        self._toc_stream = self._create_item('toc', 'toc01.html', "application/xhtml+xml", 
                                             spine=True, xattr={'properties': 'nav'})
        
        for page in pages:
            if hasattr(page, 'is_external'):
                # This is index page of docspace
                header = page.header
                self._create_chapter(page.docspace, header)
                self._add_toc_entry(page)
                
                hdr = etree.SubElement(self._page_div, 'h2')
                hdr.text = header
                
                continue
            
            if self._page_div is None:
                continue
            
            self._add_toc_entry(page)
            
            for block in page.blocks:
                el = self._render_block(block)
                if el is not None:
                    self._page_div.append(el)
        
        self._finish_chapter()
        
        self._write_toc()
        self._write_container()
        self._write_opf_file()
    
    def _write_cover(self, index, header):
        ''' Process index page:
            - Generates cover.html from index blocks and title block
            - Finds docspace names in index page to get docspace order
            - Walks index references recursively to get metadata for TOC'''
        
        stream = self._create_item('cover', 'cover.html', "application/xhtml+xml",
                                   spine=True)
        root, body = self._create_html(self.title)
        
        title = etree.SubElement(body, 'h1')
        title.text = self.title
        
        blocks = iter(index)
        for block in blocks:
            if any(isinstance(part, Reference) and part.text == '__endfrontpage__'
                   for part in block):
                break
            
            el = self._render_block(block)
            if el is not None:
                body.append(el)
        
        
        self._write_etree_stream(root, stream)
        
        self._docspaces = [docspace.docspace 
                           for docspace in index.docspaces]
        self._find_page_info(blocks)
        
    def _find_page_info(self, parts, level=1):
        for part in parts:
            if isinstance(part, ListEntry):
                level = part.level
                
            if isinstance(part, Block):
                self._find_page_info(part.parts, level)
                
            if isinstance(part, Link) and part.type == Link.INTERNAL:
                self._page_info[part.where] = (level, part.text)
    
    def _add_toc_entry(self, page):
        ''' Adds TOC entry to toc01.html and toc.ncx. Both file has hierarchial organization,
            so it takes level from _page_info cache (generated by _write_cover from index page),
            advances tree if there is not enough levels and generates TOC element as a leaf of that tree. 
            
            Tree is maintained as a pair of stacks -- for toc (HTML) and ncx files, so new element will
            be added to a last leaf element. 
            
            Also generates section for rendering page and saves it to _page_div '''
        if hasattr(page, 'is_external'):
            level = 0
            header = page.header.strip()
        else:
            level, header = self._page_info[page.page_path]
            
        name = page.page_path.replace('/', '_')
        
        # Generate section and div for this section
        section = etree.SubElement(self._page_body, 'section', {'data-type': "chapter"})
        self._page_div = etree.SubElement(section, 'div', {'id': name})
        
        self._anchor_prefix = name + '_'
        
        if self._toc_state is None:
            # initialize ncx state
            self._ncx_root = etree.Element('ncx', {'xmlns' : self.NAMESPACES['DAISY'],
                                           'version' : '2005-1'})
            head = etree.SubElement(self._ncx_root, 'head')
            
            el = etree.SubElement(head, 'meta', {'name': 'cover', 'content': 'cover'})
            etree.SubElement(head, 'meta', {'name': 'dtb:uid', 'content': self.uid})
            
            doc_title = etree.SubElement(self._ncx_root, 'docTitle')
            doc_title_text = etree.SubElement(doc_title, 'text')
            doc_title_text.text = self.title
            
            nav_map = etree.SubElement(self._ncx_root, 'navMap')
            
            # initialize toc01.html
            self._toc_root, toc_body = self._create_html('Table of contents')
            
            toc_nav = etree.SubElement(toc_body, 'nav', {'data-type': 'toc',
                                                         'id': 'id-{0}'.format(id(self._toc_root))})
            toc_ol = etree.SubElement(toc_nav, 'ol')
            
            self._toc_state = (1, [nav_map], [toc_ol])
            
        order, stack, toc_stack = self._toc_state
        
        # Create nav point
        nav_point = etree.Element('navPoint', {'id': 'np-{0}'.format(id(page)),
                                               'playOrder': str(order)})
        nav_label = etree.SubElement(nav_point, 'navLabel')
        nav_label_text = etree.SubElement(nav_label, 'text')
        nav_label_text.text = header
        
        # Generate path to anchor
        src = '{0}#{1}'.format(self._page_name, name)
        etree.SubElement(nav_point, 'content', {'src': src})
        
        # Create toc hierarchy based on index.md list hierarchy -- unwind stack
        # if we had go to upper level, and append new child to corresponding level
        while len(stack) > (level + 1):
            stack.pop()
        stack[-1].append(nav_point)
        stack.append(nav_point)
        
        # Now create an entry in html version of toc
        toc_li = etree.Element('li')
        toc_link = etree.SubElement(toc_li, 'a', {'href': src})
        toc_link.text = header
        
        while len(toc_stack) > (level + 1):
            toc_stack.pop()
        if level >= len(toc_stack):
            toc_stack.append(etree.SubElement(toc_stack[-1]._children[-1], 'ol'))
        toc_stack[-1].append(toc_li)
        
        self._toc_state = (order + 1, stack, toc_stack)
        
    def _write_toc(self):
        ''' Completes and writes toc and ncx files '''
        self._write_etree_stream(self._ncx_root, self._ncx_stream)
        self._ncx_stream = None
        
        self._write_etree_stream(self._toc_root, self._toc_stream)
        self._toc_stream = None
        
    def _write_container(self):
        ''' Generates container.xml '''
        container_xml = self.CONTAINER_XML.format(folder_name=self.FOLDER_NAME)
        self._epub.writestr(self.CONTAINER_PATH, container_xml)
    
    def _write_etree_file(self, root, fname):
        ''' Helper for writing xml directly to EPUB zip. File will be saved as fname '''
        tree_str = self.XML_HEADER
        tree_str += etree.tostring(root, encoding='utf-8')
        
        self._epub.writestr(os.path.join(self.FOLDER_NAME, fname), tree_str)
    
    def _write_etree_stream(self, root, stream, header='xml'):
        ''' Writes xml tag root to a stream of instance _ZipStream '''
        stream.write(self.XML_HEADER)
        if header == 'html':
            stream.write(self.HTML_HEADER)
        
        stream.write(etree.tostring(root, encoding='utf-8'))
    
    def _write_opf_file(self):
        ''' Generates OPF file -- literally EPUB's index. It has several sections:
            - metadata contains title, author, etc. as it was set by constructor 
            - manifest contains list of all files created by _create_item
            - spine defines order of htmls in a book. elements are added to spine if
              spine flag was set in _create_item
            - guide contains other references -- currently it is TOC and Cover references '''
        root = etree.Element('package',
                             {'xmlns' : self.NAMESPACES['OPF'],
                              'xmlns:dc' : self.NAMESPACES['DC'],
                              'unique-identifier' : self.IDENTIFIER_ID,
                              'version' : '3.0'})

        root.attrib['prefix'] = 'rendition: http://www.ipdf.org/vocab/rendition/#'

        ## METADATA
        metadata = etree.SubElement(root, 'metadata')

        el = etree.SubElement(metadata, 'meta', {'property':'dcterms:modified'})
        el.text = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        for ns_name, aname, text in self._metadata:
            if ns_name == 'DC':
                el = etree.SubElement(metadata, 'dc:' + aname, {'id': 'pub-' + aname})
                el.text = text
                
                el = etree.SubElement(metadata, 'meta', {'property': 'dcterms:' + aname,
                                                         'id': 'meta-' + aname})
                el.text = text
        
        el = etree.SubElement(metadata, 'meta', {'name': 'cover',
                                                 'content': 'cover'})

        # MANIFEST
        manifest = etree.SubElement(root, 'manifest')
        
        for id, fname, mimetype, _, xattr in self._items:
            attr = xattr.copy()
            attr.update({'id': id, 'href': fname, 'media-type': mimetype})
            el = etree.SubElement(manifest, 'item', attr)

        # SPINE
        spine = etree.SubElement(root, 'spine', {'toc': 'toc.ncx'})
        for id, _, _, is_spine, _ in self._items:
            if is_spine:
                el = etree.SubElement(spine, 'itemref', {'idref': id})
        
        # GUIDE
        guide = etree.SubElement(root, 'guide')
        etree.SubElement(guide, 'reference', {'href': 'cover.html',
                                              'type': 'cover',
                                              'title': 'Cover'})
        etree.SubElement(guide, 'reference', {'href': 'toc01.html',
                                              'type': 'toc',
                                              'title': 'Table of contents'})
        
        self._write_etree_file(root, 'content.opf')
        
    def _create_item(self, id, fname, mimetype, spine=False, unique=False, xattr={}):
        ''' Create new file inside epub:
                - id, unique -- id prefix (unique number is added if unique=True)
                - fname -- path with EPUB/ dir
                - mimetype - mime type
                - spine -- should be set to True if element is a spine
                - xattr -- extra XML attributes used in OPF manifest section 
            Returns writeable file-like object to store file's data'''
        # Create item and return stream for writing to it
        path = os.path.join(self.FOLDER_NAME, fname) 
        stream = _ZipStream(self._epub, path)
        
        if not unique:
            id += '-idp{0}'.format(hash(path))
        
        self._items.append((id, fname, mimetype, spine, xattr))
        
        return stream
    
    def _create_html(self, header):
        ''' Generates HTML skeleton and returns pair of root and body tags '''
        root = etree.Element('html', {'xmlns:epub' : self.NAMESPACES['EPUB'],
                                      'xmlns' : self.NAMESPACES['XHTML']})
                             
        head = etree.SubElement(root, 'head')
        title = etree.SubElement(head, 'title')
        title.text = header
        
        css = etree.SubElement(head, 'link', {'rel': "stylesheet",
                                              'type': "text/css",
                                              'href': "epub.css"})
        
        body = etree.SubElement(root, 'body', {'data-type': 'book'})
        
        return root, body
    
    def _get_docspace_page_name(self, docspace):
        ''' Generates name of chapter file based on docspace name '''
        return 'ch{0:02d}.html'.format(self._docspaces.index(docspace))
    
    def _create_chapter(self, docspace, header):
        ''' Creates new chapter HTML and sets _page_* variables '''
        self._page_name = self._get_docspace_page_name(docspace)
        
        stream = self._create_item('chapter', self._page_name,
                                   "application/xhtml+xml", spine=True)
        
        root, body = self._create_html(header)
        
        self._finish_chapter()
        
        self._page_stream = stream
        self._page_root = root
        self._page_body = body

    def _finish_chapter(self):
        if self._page_stream:
            self._write_etree_stream(self._page_root, self._page_stream, 'html')
            self._page_stream = None
            
    def _render_block(self, block):
        if not self.print_sources and isinstance(block, CodeListing):
            el = etree.Element('p')
            el.text = 'Source file '
            cel = etree.SubElement(el, 'a', {'href': self.SOURCE_URL + block.fname})
            cel.text = block.fname
            return el
        
        if isinstance(block, Header):
            el = etree.Element('h{0}'.format(block.size))
        elif isinstance(block, Code):
            el = etree.Element('pre', {'data-programming-language': 'perl'})
        elif isinstance(block, ListEntry):
            el = etree.Element('li')
        elif isinstance(block, ListBlock):
            el = etree.Element('ul')
        elif isinstance(block, Table):
            el = etree.Element('table')
        elif isinstance(block, TableRow):
            el = etree.Element('tr')
        elif isinstance(block, TableCell):
            el = etree.Element('td')
            if block.colspan > 1:
                el.attrib['colspan'] = str(block.colspan)
            if block.rowspan > 1:
                el.attrib['rowspan'] = str(block.rowspan)
        elif isinstance(block, BlockQuote):
            el = etree.Element('blockquote')
        elif isinstance(block, Incut):
            el = etree.Element('div',  {'class': 'incut'})
            
            etree.SubElement(el, 'hr')
            hdr = etree.SubElement(el, 'span', {'class': 'incut-{0}'.format(block.style)})
            hdr.text = self.INCUT_CLASSES[block.style]
        elif isinstance(block, Span):
            if block.style == 'small':
                el = etree.Element('small')
            elif block.style[0] == '#':
                el = etree.Element('span', {'style': 'color: {0};'.format(block.style[1:])})
        elif isinstance(block, Paragraph):
            el = etree.Element('p')
        
        for part in block:
            subel = self._render_part(part)
            if subel is None:
                continue
            el.append(subel)
        
        if isinstance(block, Incut):
            etree.SubElement(el, 'hr')
        
        return el
        
    def _render_part(self, part):
        if isinstance(part, Block):
            return self._render_block(part)
        
        def _element(tag, text=None, attrib={}):
            el = etree.Element(tag, attrib)
            if text is not None:
                el.text = text.decode('utf-8')
            return el
        
        if isinstance(part, str):
            return _element(None, part)
        elif isinstance(part, ItalicText):
            return _element('em', part.text)
        elif isinstance(part, BoldText):
            return _element('strong', part.text)
        elif isinstance(part, InlineCode):                    
            return _element('code', part.text)
        elif isinstance(part, Reference):
            return _element('a', None, {'id': self._anchor_prefix + part.text})
        elif isinstance(part, Image):
            src = self._add_image(part.where)
            return _element('img', None, {'src': src})
        elif isinstance(part, Link):
            # resolve link
            href = part.where
            if part.type == Link.INTERNAL:
                href = self._resolve_link(href)
                
            attrib = {'href': href}
            if part.type == Link.INVALID:
                attrib['style'] = "color: red"
            
            return _element('a', part.text, attrib)
        elif isinstance(part, BreakLine):
            return _element('br')
    
    def _resolve_link(self, where):
        ''' Cross-references internal link within book '''
        if '#' in where:
            name = where[:where.rfind('#')]
        else:
            name = where
            
        docspace = os.path.dirname(where)
        where = where.replace('#', '_').replace('/', '_')
        
        return '{0}#{1}'.format(self._get_docspace_page_name(docspace), 
                                where)
    
    def _add_image(self, fname):
        ''' Adds image to EPUB-book and return its path to be used in src attribute '''
        path = os.path.join('assets', fname)
        
        if fname not in self._images:
            stream = self._create_item('img', path, 'image/png')
            
            img = open(os.path.join(self.IMAGE_PATH, fname))
            stream.write(img.read())
            
            self._images.add(fname)
        
        return path
    
    def _add_css(self):
        ''' Adds epub.css to EPUB-book '''
        stream = self._create_item('epub.css', 'epub.css', 'text/css', unique=True)
        css = open(self.CSS_PATH)
        stream.write(css.read())