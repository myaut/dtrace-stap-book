import os

env = DefaultEnvironment()

AddOption('--doc-format',  dest='doc_format', action="store", default='html',
          metavar='FORMAT', help='Documentation format (markdown or html)')
AddOption('--verbose', dest='verbose', action='store_true', default=False,
          help='Be verbose')
AddOption('--no-sources', dest='no_sources', action='store_true', default=False,
          help='Do not put source files to book')


InkscapeBuilder = Builder(action = Action('inkscape -z -e $TARGET $SOURCE'),
                          suffix = '.png',
                          src_suffix = '.svg')
CompressBuilder = Builder(action = Action('convert -define png:compression-level=9 -define png:compression-strategy=0 -define png:compression-filter=0 $SOURCE $TARGET'),
                          suffix = '.png',
                          src_suffix = '.svg')
LessBuilder = Builder(action = Action('lesscpy $LESSFLAGS $SOURCE > $TARGET'),
                      suffix = '.css',
                      src_suffix = '.less')
env.Append(BUILDERS = {'InkscapeBuilder': InkscapeBuilder,
                       'LessBuilder': LessBuilder,
                       'CompressBuilder': CompressBuilder})

def ConvertSVGs(env, imgdir, width):
    img = env.Clone()
    img['PNGWIDTH'] = width
    
    for image in imgdir.glob('*.svg'):
        tgt = os.path.join('build', image.path.replace('.svg', '.png'))
        img.CompressBuilder(tgt, img.InkscapeBuilder(tgt + '.1', image))
    for image in imgdir.glob('*.png'):
        tgt = os.path.join('build', image.path)
        img.CompressBuilder(tgt, image)
        

ConvertSVGs(env, Dir('images'), 800)
ConvertSVGs(env, Dir('images').Dir('linux'), 800)
ConvertSVGs(env, Dir('images').Dir('solaris'), 800)
ConvertSVGs(env, Dir('images').Dir('conv'), 300)
ConvertSVGs(env, Dir('images').Dir('icons'), 24)

env.VariantDir('build/', 'book/')
SConscript('build/SConscript', 'env')