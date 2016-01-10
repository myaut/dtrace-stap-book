import os
import sys

env = DefaultEnvironment()

AddOption('--doc-format',  dest='doc_format', action="store", default='html',
          metavar='FORMAT', help='Documentation format (markdown or html)')
AddOption('--verbose', dest='verbose', action='store_true', default=False,
          help='Be verbose')
AddOption('--no-sources', dest='no_sources', action='store_true', default=False,
          help='Do not put source files to book')

LessBuilder = Builder(action = Action('lesscpy $LESSFLAGS $SOURCE > $TARGET'),
                      suffix = '.css',
                      src_suffix = '.less')
env.Append(BUILDERS = {'LessBuilder': LessBuilder})

VariantDir('build/book/images', 'images')
SConscript('build/book/images/SConscript', 'env')

VariantDir('build/book', 'book')
SConscript('build/book/SConscript', 'env')