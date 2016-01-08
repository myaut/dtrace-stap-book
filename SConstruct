import os

env = DefaultEnvironment()

AddOption('--doc-format',  dest='doc_format', action="store", default='html',
          metavar='FORMAT', help='Documentation format (markdown or html)')
AddOption('--verbose', dest='verbose', action='store_true', default=False,
          help='Be verbose')

InkscapeBuilder = Builder(action = Action('inkscape -z -e $TARGET $SOURCE'),
                          suffix = '.png',
                          src_suffix = '.svg')
LessBuilder = Builder(action = Action('lesscpy $LESSFLAGS $SOURCE > $TARGET'),
                      suffix = '.css',
                      src_suffix = '.less')
env.Append(BUILDERS = {'InkscapeBuilder': InkscapeBuilder,
                       'LessBuilder': LessBuilder})

def ConvertSVGs(env, imgdir, width):
    img = env.Clone()
    img['PNGWIDTH'] = width
    
    for image in imgdir.glob('*.svg'):
        tgt = os.path.join('build', image.path.replace('.svg', '.png'))
        img.InkscapeBuilder(tgt, image)
    for image in imgdir.glob('*.png'):
        tgt = os.path.join('build', image.path)
        env.Command(tgt, image, Copy("$TARGET", "$SOURCE"))
        

ConvertSVGs(env, Dir('images'), 800)
ConvertSVGs(env, Dir('images').Dir('linux'), 800)
ConvertSVGs(env, Dir('images').Dir('solaris'), 800)
ConvertSVGs(env, Dir('images').Dir('conv'), 300)
ConvertSVGs(env, Dir('images').Dir('icons'), 24)

env.VariantDir('build/', 'book/')
SConscript('build/SConscript', 'env')