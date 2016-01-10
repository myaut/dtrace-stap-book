import os
import sys

import xml.etree.ElementTree as etree

NAMESPACES = {
        '': 'http://www.w3.org/2000/svg',
        'xlink': 'http://www.w3.org/1999/xlink',
        'sodipodi': 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd',
        'inkscape': 'http://www.inkscape.org/namespaces/inkscape'
    }

def _xml_tag(tag, ns=''):
    return '{{{0}}}{1}'.format(NAMESPACES[ns], tag)

# Parse args and process
target = sys.argv[1]
source = sys.argv[2]
extrasvgs = dict((os.path.basename(fname), fname)
                 for fname in sys.argv[3:])

for ns, uri in NAMESPACES.items():
    etree.register_namespace(ns, uri)

# Parse main image
tree = etree.parse(source)
root = tree.getroot()

for group in root.findall('.//' + _xml_tag('g')):
    use = group.find(_xml_tag('use'))
    if use is None:
        continue
    
    href = use.attrib[_xml_tag('href', 'xlink')]
    
    if href not in extrasvgs:
        raise ValueError('Invalid use reference {0}'.format(href))
    
    group.clear()
    
    # Read sub svg
    extrasvg = etree.parse(extrasvgs[href]).getroot()
    extragroup = extrasvg.find(_xml_tag('g'))
    if extragroup is not None:
        group.extend(extragroup)
    
tree.write(target)