import os
import sys

from tsdoc.page import MarkdownPage
from tsdoc.blocks.html import HTMLPrinter
from tsdoc.blocks.pdf import PDFPrinter, CheatSheetTemplate
        
# Main code
_ = sys.argv.pop(0)
page_path = sys.argv.pop(0) 
out_path = sys.argv.pop(0) 

# Destination dir
doc_dir = os.path.dirname(page_path)

if out_path.endswith('.pdf'):
    printer = PDFPrinter(False, CheatSheetTemplate)
elif out_path.endswith('.html'):
    printer = HTMLPrinter(os.getenv('TSDOC_HTML_TEMPLATE'))

page = MarkdownPage(page_path)
page.header = os.getenv('TSDOC_HEADER')
page.docspace = None

with open(out_path, 'wb') as outf:
    if printer.single_doc:
        printer.do_print_pages(outf, page.header, [page])
    else:
        printer.do_print(outf, page.header, page)

