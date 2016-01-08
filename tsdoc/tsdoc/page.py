import os
import sys

from pprint import pprint

from collections import defaultdict, OrderedDict

from tsdoc import *
from tsdoc.blocks import *
from tsdoc.mdparser2 import MarkdownParser

VERBOSE = os.getenv('TSDOC_VERBOSE', None) is not None
_TRACE_DOCS = []

class TSDocProcessError(Exception):
    pass

class DocPage(object):
    HEADER_HSIZE = 1
    
    def __init__(self, docspace, name):
        self.docspace = docspace
        self.name = name
        
        self.header = ''
        
        self.page_path = '%s/%s' % (docspace, name)
        
        self.blocks = []
        self.references = {}
        
        self.nav_links = {}
        
        self.doc_path = None
    
    def __iter__(self):
        return iter(self.blocks)
    
    def __repr__(self):
        return '<%s %s/%s>' % (self.__class__.__name__,
                               self.docspace, self.name)
    
    def create_doc_path(self, doc_dir, doc_suffix):
        doc_path = os.path.join(doc_dir, self.docspace,
                                self.name + doc_suffix)     
        self.doc_path = doc_path
    
    def prep_print(self):
        if self.header:
            hobj = Header(DocPage.HEADER_HSIZE, [self.header])
            self.blocks.insert(0, Block([hobj]))
    
    def set_format(self, doc_format):
        self.format = doc_format
        
    def iter_parts(self, pred):
        ''' Generator - iteratively other all blocks/parts 
        and returns those that match predicate. 
        
        Allows to avoid recursive algorithms'''
        return self._iter_parts_block(pred, self.blocks) 
    
    def _iter_parts_block(self, pred, block, level = 0):
        for part in block:
            if pred(part):
                yield part
            
            if isinstance(part, Block):
                parts = self._iter_parts_block(pred, part, level + 1)
                for block_part in parts:
                    yield block_part
        
    
    def add_nav_link(self, nav_type, page):
        where = self.gen_link_to(page)
        self.nav_links[nav_type] = NavLink(nav_type, page, where)
        
    def gen_link_to(self, page):
        doc_dir = os.path.dirname(self.doc_path)
        return os.path.relpath(page.doc_path, doc_dir)
    
    def set_header_from_link(self, link):
        if not self.header and link.text:
            self.header = link.text
        elif self.header and not link.text:
            link.text = self.header

class MarkdownPage(DocPage):
    def __init__(self, page_path):
        path, name = os.path.split(page_path)
        _, docspace = os.path.split(path)
        
        name = name[:name.find('.')]
        
        DocPage.__init__(self, docspace, name)
        
        fp = file(page_path, 'r')
        text = fp.read()
        fp.close()
        
        parser = MarkdownParser(text, self.page_path)
        self.blocks = parser.parse()

class IncompletePage(DocPage):
    def __init__(self, page_path):
        path, name = os.path.split(page_path)
        _, docspace = os.path.split(path)
        
        DocPage.__init__(self, docspace, name)
        
        self.blocks = [Incut('WARN')]
        self.blocks[0].add('This page is not yet written. Sorry. ')
        
    def add_index_link(self, index):
        self.blocks[0].add(Link('Return to index.', Link.EXTERNAL, 
                                self.gen_link_to(index)))

class IndexPage(MarkdownPage):
    DOCSPACE_HSIZE = 3
    CHAPTER_HSIZE = 4
    REF_LETTER_HSIZE = 2
    
    INDEX_LINK_TEXT = 'Index'
    REFERENCE_LINK_TEXT = 'Reference'
    REFERENCE_HEADER = 'Reference'
    
    class DocSpaceReference(DocPage):
        def __init__(self, docspace, references, ref_prefix = ''):
            name = 'reference'
            
            DocPage.__init__(self, docspace, name)
            
            self.references = references
            self.header = IndexPage.REFERENCE_HEADER
            self.ref_prefix = ref_prefix
            
            self.links = []
            
            self._preprocess()
        
        def _preprocess(self):            
            sorted_refs = defaultdict(dict)
            
            for (ref_link, ref_part) in self.references.items():
                if isinstance(ref_part, CodeReference):
                    name = ref_part.ref_name
                    if self.ref_prefix and name.lower().startswith(self.ref_prefix):
                        realname = name[len(self.ref_prefix):]
                        first_letter = (self.ref_prefix + realname[0]).upper()
                    else:
                        first_letter = name[0].upper()
                    
                    sorted_refs[first_letter][name] = (ref_link, ref_part)
            
            for letter in sorted(sorted_refs.keys()):
                hobj = Header(IndexPage.REF_LETTER_HSIZE, [letter])
                block = Paragraph([hobj])
                
                refs = sorted_refs[letter]
                for name in sorted(refs.keys()):
                    ref_link, ref_part = refs[name]
                    
                    linkobj = Link(name, Link.INTERNAL, ref_link)
                    entry = [linkobj, ', ', ref_part.ref_class, LineBreak()]
                    
                    block.extend(entry)
                    
                    self.links.append((self, linkobj))
                
                self.blocks.append(block) 
    
    class DocSpaceIndex(DocPage):
        def __init__(self, header, docspace, is_external, gen_reference, ref_prefix = ''):
            name = 'index'
            
            DocPage.__init__(self, docspace, name)
            self.header = header
            
            self.links = []
            
            self.is_external = is_external
            self.gen_reference = gen_reference
            self.ref_prefix = ref_prefix
            
            self.reference = None
        
        def process(self, pages, docspaces):
            self.pages = pages
            self.docspaces = docspaces
            
            # Collect links and references from all pages
            for page in self.pages.values():
                links = self._collect_ref_links(page, False)
                self.links.extend(links)
            
            self.index_links = self._collect_ref_links(self, True)
            self.links.extend(self.index_links)
            
            # Generate reference
            if self.gen_reference:
                self._create_reference()
        
        def prepare(self, index):
            doc_dir = os.path.join(index.doc_dir, self.docspace)
            if not os.path.exists(doc_dir):
                os.makedirs(doc_dir)
            
            # Generate real paths 
            if self.is_external:
                pages = self.pages
                
                self.pages = OrderedDict()                
                self.pages['__index__'] = self
                
                for name, page in pages.items():
                    self.pages[name] = page
            else:
                # Main index file is real, so assume it's 
                # doc_path, so gen_link_to will think that it is 
                # located in build/doc not build/doc/<namespace>
                # and generate correct links
                self.doc_path = index.doc_path
            
            for page in self.pages.values():  
                page.prep_print()
                page.create_doc_path(index.doc_dir, index.doc_suffix)
                
        def generate(self, printer, index, joint = False):   
            if self.is_external:
                self.add_nav_link(NavLink.HOME, index)
            
            # Generate navigation links
            self._gen_nav_links(self.index_links, index)
            
            # Substitute links with references to pages
            if printer.xref_pages:
                self._xref(index)
            
            if printer.single_doc:
                if self.is_external:
                    pages = []
                    
                    for link in self.index_links:
                        pages.append(self.pages[link.where])
                    
                    stream = file(self.doc_path, 'w')
                    printer.do_print_pages(stream, self.header, pages)
            else:    
                for page in self.pages:
                    if VERBOSE:
                        print 'Generating %s...' % page.doc_path
                    if not os.path.isdir(os.path.dirname(page.doc_path)):
                        print >> sys.stderr, 'WARNING: Directory "%s" does not exist' % (os.path.dirname(page.doc_path))
                        continue
                    stream = file(page.doc_path, 'w')
                    printer.do_print(stream, self.header, page)
        
        def find_page(self, link):
            docspace_name, name = link.where.split('/')            
            docspace = self
            
            # Cut anchor
            if '#' in name:
                name = name[:name.rfind('#')]
            
            if docspace_name != self.docspace:
                for docspace in self.docspaces:
                    if docspace_name == docspace.docspace:
                        break
                else:
                    print >> sys.stderr, 'WARNING: Invalid link "%s" in docspace "%s"' % (link.where,
                                                                                          self.docspace)
                    return None 
            
            try:
                return docspace.pages[name]
            except KeyError:
                print >> sys.stderr, 'WARNING: Link "%s" not found in docspace "%s", available pages: %s' % (link.where,
                                                                                                             docspace.docspace,
                                                                                                             ', '.join(docspace.pages.keys()))
                return None
        
        def _collect_ref_links(self, page, is_index):
            def pred(part):
                return isinstance(part, Reference) or \
                       (isinstance(part, Link) and part.type == Link.INTERNAL)
            
            links = []
            
            iter_parts = page.iter_parts(pred)
            for part in iter_parts:
                if isinstance(part, Reference):
                    full_ref = '%s/%s#%s' % (page.docspace, page.name,
                                             part.text)
                    self.references[full_ref] = part
                else:
                    if is_index:
                        page.set_header_from_link(part)
                    links.append((page, part))
            
            return links
        
        def _gen_nav_links(self, index_links, index):
            for (prev, cur, next) in zip([None] + index_links[:-1],
                                         index_links, 
                                         index_links[1:] + [None]):
                cur_page = self.find_page(cur[1])
                
                if cur_page is None:
                    continue
                
                if prev is not None:
                    prev_page = self.find_page(prev[1])
                    if prev_page is not None:
                        cur_page.add_nav_link(NavLink.PREV, prev_page)
                if next is not None:
                    next_page = self.find_page(next[1])
                    if next_page is not None:
                        cur_page.add_nav_link(NavLink.NEXT, next_page)
                
                if self.is_external:    
                    cur_page.add_nav_link(NavLink.UP, self)
                    
                if self.reference is not None:
                    cur_page.add_nav_link(NavLink.REF, self.reference)
                
                cur_page.add_nav_link(NavLink.HOME, index)
            
            if self.reference:
                if self.is_external:    
                    self.reference.add_nav_link(NavLink.UP, self)
                
                self.reference.add_nav_link(NavLink.HOME, index)
        
        def _create_incomplete_page(self, index, name):
            # Create IncompletePage
            if '#' in name:
                name = name[:name.rfind('#')]                    
            page = IncompletePage(name)
            page.prep_print()
            page.create_doc_path(index.doc_dir, index.doc_suffix)
            page.add_index_link(index)
            
            self.pages[name] = page
            
            return page
            
        def _xref(self, index):
            for (refpage, link) in self.links:
                if link.type != Link.INTERNAL:
                    continue
                
                page = self.find_page(link)
                
                if page is None:
                    page = self._create_incomplete_page(index, link.where)
                
                if isinstance(page, IncompletePage):
                    link.type = Link.INVALID
                    print >> sys.stderr, 'WARNING: Not found page for link "%s" for page %s' % (link, refpage)
                else:
                    link.type = Link.EXTERNAL
                
                # Not all page headers are set in _collect_ref_links()
                # so set them here but only if reference page is an docspace index page
                if isinstance(refpage, IndexPage.DocSpaceIndex):
                    page.set_header_from_link(link)
                
                where = link.where
                if '#' in where:
                    anchor = where[link.where.rfind('#'):]
                else:
                    anchor = ''
                
                link.where = refpage.gen_link_to(page) + anchor            
        
        def _create_reference(self):
            reference = IndexPage.DocSpaceReference(self.docspace,
                                                    self.references,
                                                    self.ref_prefix)
            
            self.pages['reference'] = reference
            self.reference = reference
            
            self.links.extend(reference.links)
            
            # Generate index entry for reference
            hobj = Header(IndexPage.CHAPTER_HSIZE, [IndexPage.REFERENCE_HEADER])
            list = ListBlock()
            
            ds_ref_link = '%s/%s' % (self.docspace, 'reference')
            link = Link(IndexPage.REFERENCE_LINK_TEXT, Link.INTERNAL, ds_ref_link)
            list.add(ListEntry(1, [link]))
            
            self.blocks.append(Paragraph([hobj, list]))
            self.links.append((self, link)) 
    
    def __init__(self, page_path, doc_header, pages): 
        MarkdownPage.__init__(self, page_path)
        self.header = doc_header
        self.docspace = ''
        
        self.pages = pages
        
        self._process_index()
        
    def generate(self, printer, doc_dir, doc_suffix):
        self.doc_dir = doc_dir
        self.doc_suffix = doc_suffix
        
        self.create_doc_path(doc_dir, doc_suffix)
        
        for docspace in self.docspaces:
            docspace.prepare(self)
        
        for docspace in self.docspaces:
            docspace.generate(printer, self)     
            
            if docspace.is_external:
                # Create link to it - if it was earlier removed 
                hobj = Header(docspace.header, IndexPage.DOCSPACE_HSIZE)
                list = ListBlock()
                
                ds_index_link = '%s/%s%s' % (docspace.docspace,
                                             docspace.name,
                                             doc_suffix) 
                list.add(ListEntry(1, [Link(IndexPage.INDEX_LINK_TEXT, 
                                            Link.EXTERNAL, ds_index_link)]))
                
                self.blocks.append(Paragraph([hobj, list]))
        
        # Generate index itself
        if not printer.single_doc:
            if VERBOSE:
                print 'Generating index...'
        
            self.prep_print()
            
            stream = file(self.doc_path, 'w')
            printer.do_print(stream, self.header, self)
        else:
            pages = [self]
            
            for docspace in self.docspaces:
                if not docspace.is_external:
                    pages.append(docspace)
                    
                    for _, link in docspace.index_links:
                        where = link.where.split('/')[1]
                        pages.append(docspace.pages[where])
                
            stream = file(self.doc_path, 'w')
            printer.do_print_pages(stream, self.header, pages)
    
    def _process_index(self):
        # 1st pass - split index page into smaller indexes
        # one index per document space
        self.docspaces = []
        
        docspace_index = None
        tags = []
        header = None
        docspace = None
        
        is_external = False
        gen_reference = False
        ref_prefix = ''
        
        blocks = []
        
        for block in self.blocks[:]:
            for part in block.parts[:]:
                if isinstance(part, Header) and \
                        part.size == IndexPage.DOCSPACE_HSIZE:
                    # Found new docspace block
                    # NOTE: Header & reference tags should be within same block
                    if docspace_index is not None:
                        self.docspaces.append(docspace_index)
                    
                    header = ''.join(map(str, part.parts))
                    docspace_index = None
                    blocks = [block]
                    docspace = None
                    tags = [part.text
                            for part in part.parts 
                            if isinstance(part, Reference)]
                    
                    is_external = False
                    gen_reference = False
            
            if docspace_index is None and header is not None:
                # Process tag directives
                for tag in tags:
                    if tag == '__external_index__':
                        is_external = True
                    elif tag == '__reference__':
                        gen_reference = True
                    elif tag.startswith('__refprefix__'):
                        _, ref_prefix = tag.split(':')
                    elif tag.startswith('__docspace__'):
                        _, docspace = tag.split(':')
                    
                if not docspace:
                    print >> sys.stderr, 'WARNING: Not found __docspace__ directive for "%s"' % header
                
                if docspace not in self.pages:
                    print >> sys.stderr, 'WARNING: Not found docspace "%s"' % docspace
                    header = None
                    continue
                
                # Create new index entry
                docspace_index = IndexPage.DocSpaceIndex(header, docspace, 
                                                   is_external, gen_reference, ref_prefix)
                docspace_index.blocks = blocks
                
                header = None
            else:
                blocks.append(block)
            
            if is_external:
                self.blocks.remove(block)
        
        if docspace_index is not None:
            self.docspaces.append(docspace_index)
        
        # 2nd pass - cross reference pages and links
        for docspace_index in self.docspaces:
            docspace_name = docspace_index.docspace
            docspace_index.process(self.pages[docspace_name], self.docspaces)