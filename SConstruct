import os
import sys

env = DefaultEnvironment()

AddOption('--doc-format',  dest='doc_format', action="store", default='html',
          metavar='FORMAT', help='Documentation format (markdown or html)')
AddOption('--verbose', dest='verbose', action='store_true', default=False,
          help='Be verbose')
AddOption('--no-sources', dest='no_sources', action='store_true', default=False,
          help='Do not put source files to book')

def _inkscape_builder(opt, suffix):
    return Builder(action = Action('inkscape -z %s $TARGET $SOURCE' % opt),
                   suffix = suffix, src_suffix = '.svg')

InkscapeBuilder = _inkscape_builder('-e', '.svg.png')
InkscapeSVGBuilder = _inkscape_builder('-l', '.plain.svg')
InkscapePDFBuilder = _inkscape_builder('-A', '.pdf')
CheatSheetBuilder = Builder(action = Action('%s cheatsheet/gen-cheatsheet.py $TARGET $SOURCE' % (sys.executable)),
                             suffix = '.pdf',
                             src_suffix = '.svg')
CompressBuilder = Builder(action = Action('convert -define png:compression-level=9 -define png:compression-strategy=0 -define png:compression-filter=0 $SOURCE $TARGET'),
                          suffix = '.png',
                          src_suffix = '.svg')
LessBuilder = Builder(action = Action('lesscpy $LESSFLAGS $SOURCE > $TARGET'),
                      suffix = '.css',
                      src_suffix = '.less')
env.Append(BUILDERS = {'InkscapeBuilder': InkscapeBuilder,
                       'InkscapeSVGBuilder': InkscapeSVGBuilder,
                       'InkscapePDFBuilder': InkscapePDFBuilder,
                       'LessBuilder': LessBuilder,
                       'CompressBuilder': CompressBuilder})

def ConvertSVGs(env, imgdir, width):
    img = env.Clone()
    img['PNGWIDTH'] = width
    
    for image in imgdir.glob('*.svg'):
        tgt = os.path.join('build', image.path.replace('.svg', ''))
        img.CompressBuilder(tgt, img.InkscapeBuilder(tgt, image))
        img.InkscapeSVGBuilder(tgt, image)
        img.InkscapePDFBuilder(tgt, image)
    for image in imgdir.glob('*.png'):
        tgt = os.path.join('build', image.path)
        img.CompressBuilder(tgt, image)
        

ConvertSVGs(env, Dir('images'), 800)
ConvertSVGs(env, Dir('images').Dir('linux'), 800)
ConvertSVGs(env, Dir('images').Dir('solaris'), 800)
ConvertSVGs(env, Dir('images').Dir('conv'), 300)
ConvertSVGs(env, Dir('images').Dir('icons'), 24)

# Render cheat sheets
# TODO: alias
for image in Dir('cheatsheet').glob('*.svg'):
    svg = os.path.join('build', image.path.replace('.svg', '.plain.svg'))
    pdf = os.path.join('build', image.path.replace('.svg', '.pdf'))
    
    env.InkscapeSVGBuilder(svg, image)
    tgt = env.CheatSheetBuilder(pdf, svg)
    
    env.Depends(tgt, Dir('images').glob('*.svg'))

env.VariantDir('build/', 'book/')
SConscript('build/SConscript', 'env')