#BUILTMODULE

import weakref
import os
from collections import OrderedDict
from collections.abc import Mapping
import inspect
import warnings

import wordhash
from wordhash import random

from ..utilities import Grouper, make_hash, w_hash
from .. import disk
from ..weaklist import WeakList
from ..anchor import Anchor, _namepath_process, NoActiveAnchorError
from ..globevars import _BUILTTAG_, _CLASSTAG_, _GHOSTTAG_
from ..vectors import SchemaIterator

from ..exceptions import EverestException
class BuiltException(EverestException):
    pass
class MissingMethod(BuiltException):
    pass
class MissingAttribute(BuiltException):
    pass
class MissingKwarg(BuiltException):
    pass
class NotOnDiskError(EverestException):
    '''That hashID could not be found at the provided location.'''
    pass

# BUFFERSIZE = 5 * 2 ** 30 # i.e. 5 GiB
# def buffersize_exceeded():
#     nbytes = 0
#     for builtID, built in sorted(Meta._prebuilts.items()):
#         nbytes += built.nbytes
#     return nbytes > BUFFERSIZE

def load_built(hashID, name, path = '.'):
    with Anchor(name, path):
        return BuiltProxy(_BUILTTAG_ + hashID).realised
def load_class(typeHash, name, path = '.'):
    with Anchor(name, path):
        return ClassProxy(_CLASSTAG_ + typeHash).realised

def _get_default_inputs(func):
    parameters = inspect.signature(func).parameters
    out = parameters.copy()
    if 'self' in out: del out['self']
    for key, val in out.items():
        default = val.default
        if default is inspect.Parameter.empty:
            default = None
        out[key] = default
    argi = 0
    for key, val in parameters.items():
        if str(val)[:1] == '*':
            del out[key]
        # elif str(val)[:1] == '*':
        #     del out[key]
        #     out['arg' + str(argi)] = val
        #     argi += 1
    out = OrderedDict(out)
    return out

def sort_inputKeys(func):
    ghostTag = _GHOSTTAG_
    ghostCatTag = '(' + ghostTag + ')'
    initsource = inspect.getsource(func).split('\n')
    initsource = [line.strip() for line in initsource]
    initsource = initsource[1:initsource.index('):')]
    catsDict = OrderedDict({None: []})
    ghostCatsDict = OrderedDict({None: []})
    tag = None
    appendList = catsDict[None]
    for line in initsource:
        if line[0] == '#':
            tag = line[2:].lower()
            if tag == ghostTag:
                appendList = ghostCatsDict[None]
            elif tag.endswith(ghostCatTag):
                tag = tag[:-len(ghostCatTag)].strip()
                if not tag in ghostCatsDict:
                    ghostCatsDict[tag] = []
                appendList = ghostCatsDict[tag]
            else:
                if not tag in catsDict:
                    catsDict[tag] = []
                appendList = catsDict[tag]
        else:
            key = line.split('=')[0].strip()
            if key.startswith(ghostTag):
                assert not appendList in catsDict.values()
                key = key[len(ghostTag):]
                ghostCatsDict[None].append(key)
            appendList.append(key)
    catsDict['all'] = [i for k, sl in catsDict.items() for i in sl]
    ghostCatsDict['all'] = [i for k, sl in ghostCatsDict.items() for i in sl]
    catsDict = OrderedDict(
        [(key, tuple(val)) for key, val in catsDict.items()]
        )
    ghostCatsDict = OrderedDict(
        [(key, tuple(val)) for key, val in ghostCatsDict.items()]
        )
    return catsDict, ghostCatsDict


class Meta(type):

    _preclasses = weakref.WeakValueDictionary()
    _prebuilts = weakref.WeakValueDictionary()

    _hashDepth = 2

    _anchorManager = Anchor

    @classmethod
    def _type_hash(cls, arg):
        rawHash = make_hash(arg)
        neatHash = wordhash.get_random_proper(
            cls._hashDepth,
            randomseed = rawHash
            )
        return neatHash
    @staticmethod
    def _hash_ID(typeHash, inputsHash):
        return ':'.join([typeHash, inputsHash])

    def __new__(cls, name, bases, dic):
        outCls = super().__new__(cls, name, bases, dic)
        if hasattr(outCls, '_swapscript'):
            script = outCls._swapscript
        else:
            script = disk.ToOpen(inspect.getfile(outCls))()
        typeHash = Meta._type_hash(script)
        try:
            outCls = cls._preclasses[typeHash]
            assert outCls.script == script
            return outCls
        except KeyError:
            outCls.typeHash = typeHash
            outCls.script = script
            outCls.defaultInps = _get_default_inputs(outCls.__init__)
            outCls.defaultInputsHash = outCls._inputs_hash(outCls.defaultInps)
            outCls.defaultHashID = cls._hash_ID(
                outCls.typeHash, outCls.defaultInputsHash
                )
            try:
                outCls._sortedInputKeys, outCls._sortedGhostKeys = \
                    sort_inputKeys(outCls.__init__)
            except ValueError:
                outCls._sortedInputKeys, outCls._sortedGhostKeys = {}, {}
            outCls._custom_cls_fn()
            cls._preclasses[outCls.typeHash] = outCls
            return outCls

    @staticmethod
    def _align_inputs(cls, *args, **kwargs):
        inputs = cls.defaultInps.copy()
        inputs.update(kwargs)
        for arg, key in zip(args, list(inputs)[:len(args)]):
            inputs[key] = arg
        return inputs

    def __call__(cls, *args, unique = False, **kwargs):
        inputs = Meta._align_inputs(cls, *args, **kwargs)
        obj = cls.__new__(cls, unique = unique, **inputs)
        if unique:
            obj.__init__(**obj.inputs)
            return obj
        else:
            try:
                obj = cls._get_prebuilt(obj.inputsHash)
                # warnings.warn("Loading pre-built object.")
            except KeyError:
                cls._prebuilts[obj.instanceHash] = obj
                obj.__init__(**obj.inputs)
            return obj

    def __getitem__(cls, arg):
        return SchemaIterator(cls, arg)

# class O:
#     def __init__(self, cls):
#         self.cls = cls
#     def __getitem__(self, arg):
#         return SchemaIterator(self.cls, **arg)

class Built(metaclass = Meta):

    _hashDepth = 2

    def copy(self):
        return type(self)(unique = True, **self.inputs)

    @classmethod
    def _custom_cls_fn(cls):
        # designed to be overridden
        pass

    @classmethod
    def _inputs_hash(cls, arg):
        rawHash = make_hash(arg)
        neatHash = wordhash.get_random_english(
            cls._hashDepth,
            randomseed = rawHash
            )
        return neatHash
    @classmethod
    def _process_inputs(cls, inputs):
        for key, val in sorted(inputs.items()):
            if isinstance(val, Proxy):
                inputs[key] = val.realise()
        return inputs
    @classmethod
    def _process_ghosts(cls, ghosts):
        for key, val in sorted(ghosts.items()):
            if isinstance(val, Proxy):
                ghosts[key] = val.realise()
        return ghosts
    @classmethod
    def _get_inputs(cls, inputs = dict()):
        allinputs = OrderedDict(cls.defaultInps)
        allinputs.update(inputs)
        ghostKeys = cls._sortedGhostKeys['all']
        inputs = OrderedDict(
            [(k, v) for k, v in allinputs.items() if not k in ghostKeys]
            )
        ghosts = OrderedDict(
            [(k, v) for k, v in allinputs.items() if k in ghostKeys]
            )
        inputs = cls._process_inputs(inputs)
        ghosts = cls._process_ghosts(ghosts)
        return inputs, ghosts

    @classmethod
    def _get_prebuilt(cls, inputsHash):
        k = ':'.join([cls.typeHash, inputsHash])
        return cls._prebuilts[k]

    def __new__(cls, unique = False, **inputs):

        inputs, ghosts = cls._get_inputs(inputs)
        inputsHash = cls._inputs_hash(inputs)
        obj = super().__new__(cls)
        obj.inputs = inputs
        obj.ghosts = ghosts
        obj.inputsHash = inputsHash
        obj.hashID = type(cls)._hash_ID(obj.typeHash, obj.inputsHash)
        if unique:
            instanceSuffix = str(random.randint(18))
            obj.instanceHash = obj.hashID + ';' + instanceSuffix
        else:
            obj.instanceHash = obj.hashID

        obj.rootObjects = {
            cls.typeHash: {_CLASSTAG_: cls.script}
            }
        obj.globalObjects = {
            # 'classes': {cls.typeHash: cls}
            }
        obj.localObjects = {
            'typeHash': obj.typeHash,
            'inputsHash': obj.inputsHash,
            'hashID': obj.hashID,
            'inputs': obj.inputs,
            # 'class': cls
            }
        obj._proxy = lambda: None

        return obj

    def __init__(self, **customAttributes):

        self.localObjects.update(customAttributes)
        self.localObjects['type'] = type(self).__name__

        self._pre_anchor_fns = WeakList()
        self._post_anchor_fns = WeakList()

        self.inputs = Grouper(self.inputs) # <- may be problematic!

        super().__init__()

    @classmethod
    def anchor(cls, name, path):
        return cls.__class__._anchorManager(name, path)
    @property
    def man(self):
        return self.__class__._anchorManager.get_active()
    @property
    def name(self):
        return self.man.name
    @property
    def path(self):
        return self.man.path
    @property
    def writer(self):
        return self.man.writer.sub(self.typeHash, self.inputsHash)
    @property
    def reader(self):
        return self.man.reader.sub(self.typeHash, self.inputsHash)
    @property
    def globalwriter(self):
        return self.man.globalwriter
    @property
    def globalreader(self):
        return self.man.globalreader
    @property
    def rootwriter(self):
        return self.man.rootwriter
    @property
    def rootreader(self):
        return self.man.rootreader
    @property
    def h5filename(self):
        man = self.__class__._anchorManager.get_active()
        return self.man.h5filename
    def touch(self, name = None, path = None):
        conds = [o is None for o in (name, path)]
        if any(conds) and not all(conds):
            raise ValueError
        if not any(conds):
            with self.anchor(name, path) as anchor:
                self._touch()
        else:
            self._touch()
    @disk.h5filewrap
    def _touch(self):
        for fn in self._pre_anchor_fns: fn()
        self.writer.add_dict(self.localObjects)
        self.rootwriter.add_dict(self.rootObjects)
        self.globalwriter.add_dict(self.globalObjects)
        for fn in self._post_anchor_fns: fn()
    @classmethod
    def touch_class(cls, name = None, path = None):
        conds = [o is None for o in (name, path)]
        if any(conds) and not all(conds):
            raise ValueError
        if not any(conds):
            with cls.anchor(name, path) as anchor:
                cls._touch_class()
        else:
            cls._touch_class()
    @classmethod
    def _touch_class(cls):
        man = cls.__class__._anchorManager.get_active()
        man.writer.add_dict({cls.typeHash: {_CLASSTAG_: cls.script}})

    def __hash__(self):
        return int(make_hash(self.instanceHash))

    def __eq__(self, arg):
        return self.hashID == arg
    def __lt__(self, arg):
        return self.hashID < arg

    @property
    def proxy(self):
        _proxy = self._proxy()
        if not _proxy is None:
            return _proxy
        else:
            _proxy = BuiltProxy(self.__class__, {**self.inputs})
            self._proxy = weakref.ref(_proxy)
            return _proxy

    def __reduce__(self):
        kwargs = dict()
        try:
            self.touch()
        except NoActiveAnchorError:
            pass
        return (_custom_unpickle, (self.proxy, kwargs))

def _custom_unpickle(proxy, kwargs):
    return proxy.realise(**kwargs)

class ProxyException(EverestException):
    pass
class NotAProxyTag(ProxyException):
    pass
class Proxy:
    def __init__(self, meta = None):
        if meta is None:
            meta = Meta
        self.meta = meta
        self._realised = None
    @staticmethod
    def _process_tag(inp, tag):
        if type(inp) is str:
            if inp.startswith(tag):
                processed = inp[len(tag):]
                assert len(processed) > 0
                return processed
        raise NotAProxyTag
    def realise(self, unique = False):
        if unique:
            return self._realise(unique = unique)
        else:
            if self._realised is None:
                self._realised = self._realise()
            return self._realised
    @property
    def realised(self):
        return self.realise()
    # def __getattr__(self, key):
    #     return getattr(self.realised, key)
    @property
    def man(self):
        return self.meta._anchorManager.get_active()
    @property
    def reader(self):
        return self.man.reader
    @property
    def hashID(self):
        return self._hashID()
class ClassProxyException(ProxyException):
    pass
class ClassProxy(Proxy):
    def __init__(self, inp, **kwargs):
        Proxy.__init__(self, **kwargs)
        if type(inp) is self.meta:
            self.typeHash = inp.typeHash
            self.script = inp.script
        elif type(inp) is str:
            try:
                inp = self._process_tag(inp, _CLASSTAG_)
                self.typeHash = inp
            except NotAProxyTag:
                self.script = inp
                self.typeHash = self.meta._type_hash(self.script)
        else:
            raise TypeError
    def _realise(self):
        try:
            return self.meta._preclasses[self.typeHash]
        except KeyError:
            if not hasattr(self, 'script'):
                self.script = self.reader[_CLASSTAG_]
            return disk.local_import_from_str(self.script).CLASS
    @property
    def reader(self):
        return super().reader.sub(self.typeHash)
    def _hashID(self):
        return self.typeHash
    def __call__(self, *args, **kwargs):
        return self.realised(*args, **kwargs)
class BuiltProxyException(ProxyException):
    pass
class NotEnoughInformation(BuiltProxyException):
    pass
class BuiltProxy(Proxy):
    def __init__(self, inp1, inp2 = None, **kwargs):
        Proxy.__init__(self, **kwargs)
        if inp2 is None:
            if not type(inp1) is str:
                raise TypeError
            inp1 = self._process_tag(inp1, _BUILTTAG_)
            typeHash, inputsHash = inp1.split(':')
            clsproxy = ClassProxy(_CLASSTAG_ + typeHash)
        else:
            if type(inp1) is ClassProxy:
                clsproxy = inp1
            else:
                clsproxy = ClassProxy(inp1)
            if type(inp2) is str:
                try:
                    inputsHash = self._process_tag(inp2, _BUILTTAG_)
                except NotAProxyTag:
                    inputsHash = inp2
            elif isinstance(inp2, Mapping):
                self.inputs, self.ghosts = clsproxy.realised._get_inputs(inp2)
                inputsHash = clsproxy.realised._inputs_hash(self.inputs)
            else:
                raise TypeError(type(inp2))
        self.clsproxy = clsproxy
        self.inputsHash = inputsHash
        self.typeHash = clsproxy.typeHash
    def _realise(self, unique = False):
        cls = self.clsproxy.realised
        try:
            return cls._get_prebuilt(self.inputsHash)
        except KeyError:
            if not hasattr(self, 'inputs'):
                self.inputs = self.reader['inputs']
            if hasattr(self, 'ghosts'):
                inputs = {**self.inputs, **self.ghosts}
            else:
                inputs = self.inputs
            return cls(unique = unique, **inputs)
    @property
    def reader(self):
        return super().reader.sub(self.typeHash, self.inputsHash)
    def _hashID(self):
        return ':'.join([self.typeHash, self.inputsHash])
