env = DefaultEnvironment()

AddOption('--doc-format',  dest='doc_format', action="store", default='html',
          metavar='FORMAT', help='Documentation format (markdown or html)')
AddOption('--verbose', dest='verbose', action='store_true', default=False,
          help='Be verbose')

env.VariantDir('build/', 'book/')
SConscript('build/SConscript', 'env')