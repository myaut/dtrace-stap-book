import json
import string

import sys

class Definition(object):
    __tsdoc_weight__ = -100
    
    # Classes
    DEF_UNKNOWN = -1
    DEF_DESCRIPTION = 0
    DEF_VARIABLE = 1
    DEF_CONSTANT = 2
    DEF_FUNCTION = 3
    DEF_TYPE = 4
    
    def_class = DEF_UNKNOWN
    
    def __init__(self):
        self.code = ''
        self.name = ''
        self.tags = []
        
        self.source = ''
        self.lineno = -1
    
    def set_source(self, source, lineno):
        self.source = source
        self.lineno = lineno
        
    def set_name(self, name):
        if isinstance(name, str):
            name = name.strip()
        self.name = name
        
    def set_code(self, code):
        self.code = code
    
    @staticmethod
    def _serialize_object(value):
        if isinstance(value, list):
            return map(Definition._serialize_object, value)
        elif isinstance(value, Definition):
            return value.serialize(is_root = False)
        
        return value
    
    def serialize(self, is_root = True):
        klass = self.__class__
        object = {'class': klass.__name__,
                  'name': self.name}
        
        if is_root:
            object.update({'code': self.code,
                           'source': self.source,
                           'lineno': self.lineno})
        
        for field in klass.__tsdoc_fields__:
            value = getattr(self, field)
            object[field] = Definition._serialize_object(value)
        
        return object
    
    def post_deserialize(self):
        pass
        
class DocText(Definition):
    def_class = Definition.DEF_DESCRIPTION
    
    class Param(Definition):
        __tsdoc_fields__ = ['type', 'name', 'description']
        
        ARGUMENT = 0
        MEMBER   = 1
        VALUE    = 2
        
        def __init__(self, type, name, description):
            Definition.__init__(self)
            
            self.type = type
            self.name = name
            self.description = description
    
    class Note(Definition):
        __tsdoc_fields__ = ['type', 'note']
        
        TEXT      = 0
        NOTE      = 1
        RETURN    = 2
        REFERENCE = 3
        
        def __init__(self, type, note):
            Definition.__init__(self)
            
            self.type = type
            self.note = note
    
    __tsdoc_fields__ = ['params', 'notes']
    __tsdoc_weight__ = 0
    
    def __init__(self):
        Definition.__init__(self)
        
        self.module = None
        self.params = [] 
        self.notes = []
    
    def add_param(self, type, name, description):
        self.params.append(DocText.Param(type, name, description))
    
    def get_params(self, type):
        return [param
                for param 
                in self.params
                if param.type == type]
    
    def add_note(self, type, note):
        self.notes.append(DocText.Note(type, note))
    
    def get_notes(self, type):
        return [note
                for note 
                in self.notes
                if note.type == type]
    
    def set_module(self, module):
        self.module = module
        
class TypeVar(Definition):
    __tsdoc_fields__ = ['types', 'tv_class', 'value']
    __tsdoc_weight__ = 10
    
    VARIABLE = 0
    ARGUMENT = 1
    TYPEDEF = 2
    
    def __init__(self):
        Definition.__init__(self)
        
        self.types = []
        self.value = None
        self.tv_class = TypeVar.VARIABLE
    
    def add_type(self, name):
        self.types.append(name)
        
    def set_value(self, value):
        self.value = value
        
    def set_class(self, tv_class):
        self.tv_class = tv_class
        
        if tv_class == TypeVar.TYPEDEF:
            self.def_class = Definition.DEF_TYPE
        else:
            self.def_class = Definition.DEF_VARIABLE
    
    def post_deserialize(self):
        return self.set_class(self.tv_class)
        
class Function(Definition):
    __tsdoc_fields__ = ['retvalue', 'args', 'specifiers']
    __tsdoc_weight__ = 100
    
    def_class = Definition.DEF_FUNCTION
    
    def __init__(self):
        Definition.__init__(self)
        
        self.retvalue = []
        self.args = []
        self.specifiers = []
    
    def add_arg(self, arg):
        self.args.append(arg)
    
    def add_retvalue(self, retvalue):
        self.retvalue.append(retvalue)
        
    def set_specifiers(self, specifiers):
        self.specifiers = specifiers

    def add_type(self, type):
        self.types.append(type)

class Macro(Definition):
    __tsdoc_fields__ = []
    __tsdoc_weight__ = 100
    
    def_class = Definition.DEF_FUNCTION

class Enumeration(Definition):    
    __tsdoc_fields__ = ['values', 'aliases']
    __tsdoc_weight__ = 50
    
    def_class = Definition.DEF_TYPE
    
    def __init__(self):
        Definition.__init__(self)
        
        self.values = []
        self.aliases = []
    
    def add_value(self, value):
        self.values.append(value)
    
    def set_aliases(self, aliases):
        self.aliases = aliases

class ComplexType(Definition):
    __tsdoc_fields__ = ['members', 'aliases', 'type']
    __tsdoc_weight__ = 50
    
    STRUCT = 1
    UNION = 2
    
    def_class = Definition.DEF_TYPE
    
    def __init__(self):
        Definition.__init__(self)
        
        self.type = 0
        self.members = []
        self.aliases = []
    
    def set_type(self, type):
        self.type = type
    
    def add_member(self, member):
        self.members.append(member)
        
    def set_aliases(self, aliases):
        self.aliases = aliases
        
class Value(Definition):
    __tsdoc_fields__ = ['value']
    __tsdoc_weight__ = 20
    
    def_class = Definition.DEF_CONSTANT
    
    def __init__(self):
        Definition.__init__(self)
        
        self.value = None
    
    def set_value(self, value):
        self.value = value

_def_classes_root = [DocText, TypeVar, Function, Macro,
                     Enumeration, ComplexType, Value]

_def_classes = dict((klass.__name__, klass) 
                    for klass in _def_classes_root)
_def_classes['Param'] = DocText.Param
_def_classes['Note'] = DocText.Note

class DefinitionGroup:
    def __init__(self, defs):
        self.defs = defs
    
    def __iter__(self):
        return iter(self.defs)
    
    def get_names(self):
        names = []
        
        for defobj in self.defs:
            name = defobj.name
            if isinstance(name, list):
                name = ' '.join(name)
            if name:
                names.append(name)
        
        return set(names)
    
    def header(self):
        for defobj in self.defs:
            if isinstance(defobj, DocText) and defobj.name:
                return defobj.name
        
        return ', '.join(self.get_names())
    
    def get_weight(self):
        return max(defobj.__tsdoc_weight__
                   for defobj in self.defs)
        
    def find_leaders(self):
        weight = -1000
        leaders = []
        
        for defobj in self.defs:
            if defobj.__tsdoc_weight__ > weight:
                weight = defobj.__tsdoc_weight__
                leaders = [defobj]
            elif defobj.__tsdoc_weight__ == weight:
                leaders.append(defobj)
        
        return leaders
    
    def merge(self, other):
        for defobj in other.defs:
            if isinstance(defobj, DocText):
                self.defs.insert(0, defobj)
    
    def split(self, names):
        defs = self.defs[:]
        new_defs = []
        
        for defobj in self.defs:
            if defobj.name in names:
                self.defs.remove(defobj)
                new_defs.append(defobj)
        
        return DefinitionGroup(new_defs)
    
    def serialize(self):
        def_list = []
        for defobj in self.defs:
            def_list.append(defobj.serialize())
        
        return def_list
    
    def have_doctext(self):
        return any(isinstance(defobj, DocText) 
                   for defobj in self.defs)

class TSDoc:
    def __init__(self, module, groups, sources = [], header = None, docspace = ''):
        self.module = module
        self.groups = groups
        self.sources = sources
        self.header = header
        self.docspace = docspace
    
    def find_header(self):
        self.header = self.module
        
        for group in self.groups:
            for defobj in group.defs:
                if not isinstance(defobj, DocText):
                    continue
                
                if defobj.module is not None:
                    self.header = defobj.module
                    return
    
    def set_docspace(self, docspace):
        self.docspace = docspace
    
    def set_sources(self, sources):
        self.sources = sources
    
    def serialize(self):
        groups = [group.serialize() 
                  for group in self.groups]
        
        node = {'module': self.module,
                'docspace': self.docspace,
                'header': self.header,
                'sources': self.sources,
                'groups': groups }
        
        return node

    @staticmethod
    def _deserialize_object(obj):
        if isinstance(obj, list):
            return map(TSDoc._deserialize_object, obj)
        elif isinstance(obj, dict):
            klass_name = obj['class']
            klass = _def_classes[klass_name]
            
            defobj = klass.__new__(klass)
            
            fields = klass.__tsdoc_fields__ + ['name']
            opt_fields = ['code', 'source', 'line']
            
            for field in fields + opt_fields:
                if field not in obj and field in opt_fields:
                    continue
                obj1 = obj[field]
                obj1 = TSDoc._deserialize_object(obj1)
                
                setattr(defobj, field, obj1)
            
            defobj.post_deserialize()
            
            return defobj
        
        return obj
    
    @staticmethod
    def deserialize(uobj):
        obj = dict([(str(k), v) for k, v in uobj.items()])
        
        tsdoc = TSDoc(**obj)
        groups = []
        
        for groupdecl in tsdoc.groups:
            defs = []
            for defdecl in groupdecl:
                defobj = TSDoc._deserialize_object(defdecl)
                defs.append(defobj)
            groups.append(DefinitionGroup(defs))
        
        tsdoc.groups = groups
        return tsdoc