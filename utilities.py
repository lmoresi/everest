import collections
from collections.abc import Mapping, Sequence
from collections import OrderedDict
import inspect
import numpy as np
import hashlib
import warnings
import pickle

import wordhash
w_hash = wordhash.w_hash

from simpli import message

from .exceptions import EverestException
class GrouperSetAttrForbidden(EverestException):
    '''
    Cannot set attributes on Grouper objects after creation. \
    Disable this lock by changing the 'lock' attribute to False.
    '''

class Grouper:
    def __init__(self, grouperDict):
        if isinstance(grouperDict, Grouper):
            grouperDict = grouperDict.grouperDict
        grouperDict = OrderedDict(grouperDict.copy())
        for key in grouperDict:
            if ' ' in key:
                val = grouperDict[key]
                del grouperDict[key]
                newKey = key.replace(' ', '_')
                grouperDict[newKey] = val
        self.__dict__.update(grouperDict)
        self.__dict__['grouperDict'] = grouperDict
        self.__dict__['lock'] = False
    def __getitem__(self, key):
        return self.grouperDict[key]
    def __setitem__(self, key, arg):
        setattr(self, key, arg)
    def __delitem__(self, key):
        delattr(self, key)
    def keys(self, *args, **kwargs):
        return self.grouperDict.keys(*args, **kwargs)
    def items(self, *args, **kwargs):
        return self.grouperDict.items(*args, **kwargs)
    def __setattr__(self, name, value):
        try:
            self._lockcheck(name)
            super().__setattr__(name, value)
            self.grouperDict[name] = value
        except GrouperSetAttrForbidden:
            warnings.warn(
                "Setting of name " + name + " on Grouper is prohibited.")
    def __delattr__(self, name):
        try:
            self._lockcheck(name)
            super().__delattr__(name)
            del self.grouperDict[name]
        except GrouperSetAttrForbidden:
            warnings.warn(
                "Deleting of name " + name + " on Grouper is prohibited.")
    def _lockcheck(self, name = None):
        if hasattr(self, 'lock'):
            if self.lock and not name == 'lock':
                raise GrouperSetAttrForbidden
        if name[:2] == name[-2:] == '__':
            raise GrouperSetAttrForbidden
        if name in dir(Grouper):
            raise GrouperSetAttrForbidden
    def copy(self):
        return self.__class__(self.grouperDict.copy())
    def update(self, inDict, silent = False):
        if silent:
            for key in list(inDict.keys()):
                try:
                    self._lockcheck(key)
                except GrouperSetAttrForbidden:
                    del inDict[key]
        if isinstance(inDict, Grouper):
            inDict = inDict.grouperDict
        for key, val in sorted(inDict.items()):
            setattr(self, key, val)
    def clear(self):
        for name in self.grouperDict.keys():
            delattr(self, name)
    def __contains__(self, key):
        return key in self.grouperDict
    def __repr__(self):
        return 'Grouper{' + str(self.grouperDict) + '}'
    @property
    def hashID(self):
        return w_hash(sorted(self.grouperDict.items()))

def prettify_nbytes(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

def is_numeric(arg):
    try:
        _ = arg + 1
        return True
    except:
        return False

def make_hash(obj):
    try:
        return get_hash(obj, make = False)
    except HashIDNotFound:
        pass
    return wordhash.make_hash(obj)

class HashIDNotFound(EverestException):
    pass
def get_hash(obj, make = True):
    if 'hashID' in dir(obj):
        hashVal = obj.hashID
    elif 'typeHash' in dir(obj):
        hashVal = obj.typeHash
    else:
        if make:
            hashVal = w_hash(obj)
        else:
            raise HashIDNotFound
    return hashVal

def _obtain_dtype(object):
    if type(object) == np.ndarray:
        dtype = object.dtype
    else:
        dtype = type(object)
    return dtype

def unique_list(listlike, func = None):
    if func is None: func = lambda e: True
    return OrderedDict(
        {e: None for e in listlike if func(e)}
        ).keys()

def flatten_dict(d, parent_key = '', sep = '_'):
    # by Imran@stackoverflow
    items = []
    parent_key = parent_key.strip(sep)
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def _unflatten_dict(host, key, val):
    splitkey = key.split('/')
    if len(splitkey) == 1:
        host[key] = val
    else:
        primekey, remkey = splitkey[0], '/'.join(splitkey[1:])
        if not primekey in host:
            host[primekey] = dict()
        process_dict(host[primekey], remkey, val)

def unflatten_dict(d):
    processed = dict()
    for key, val in sorted(d.items()):
        _unflatten_dict(processed, key, val)
    return processed

class WeakOrderedDict(OrderedDict):
    def __setitem__(self, key, arg):
        if not arg is None:
            arg = weakref.ref(arg)
        super().__setitem__(key, arg)
    def __getitem__(self, key):
        out = super().__getitem__(key)
        if out is None:
            return out
        return out()
