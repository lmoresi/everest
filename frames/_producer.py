import numpy as np
import math
from functools import wraps, partial
from collections.abc import Mapping
from collections import OrderedDict
import warnings
import time

import wordhash
from h5anchor import Reader, Writer, disk
from h5anchor.array import AnchorArray
# import reseed

from . import Frame, casemethod
from ..exceptions import *
from ..utilities import prettify_nbytes

class ProducerException(EverestException):
    pass
class ProducerNoStorage(ProducerException):
    pass
class ProducerIOError(ProducerException):
    pass
class SaveFail(ProducerIOError):
    pass
class LoadFail(ProducerIOError):
    pass
class ProducerSaveFail(SaveFail):
    pass
class ProducerLoadFail(LoadFail):
    pass
class ProducerNothingToSave(ProducerSaveFail):
    pass
class AbortStore(ProducerException):
    pass
# class ProducerMissingAsset(exceptions.MissingAsset):
#     pass

class StorageException(ProducerException):
    pass
class StorageAlreadyStored(StorageException):
    pass
class StorageAlreadyCleared(StorageException):
    pass
class NullValueDetected(StorageException):
    pass
class OutsNull:
    pass

def _get_data_properties(v):
    if v is None: return float, ()
    elif isinstance(v, np.ndarray): return v.dtype.type, v.shape
    else: return type(v), ()

class Storage(Mapping):
    def __init__(self,
            keys,
            vals,
            types,
            name = 'default',
            blocklen = int(1e6)
            ):
        storedList = list()
        for k, v, t in zip(keys, vals, types):
            shape = v.shape if isinstance(v, np.ndarray) else ()
            storedList.append(np.empty((blocklen, *shape), t))
        self.storedList = storedList
        self.stored = OrderedDict(zip(keys, self.storedList))
        self.keys = self.stored.keys
        self.blocklen = blocklen
        self.storedCount = 0
        self.name = name
    def store(self, outs):
        for s, v in zip(self.storedList, outs):
            s[self.storedCount] = v.data
        self.storedCount += 1
            # try:
            #
            # except AttributeError:
            #     s[self.storedCount] = v
    def __len__(self):
        return self.storedCount
    def __getitem__(self, key):
        try: return self.stored[key][:self.storedCount]
        except KeyError: pass
        try: return self.storedList[key][:self.storedCount]
        except (TypeError, IndexError): pass
        raise KeyError
    def __iter__(self):
        return iter(self.stored)
    def clear(self, silent = False):
        self.storedCount = 0
    def retrieve(self, index):
        for k in self:
            yield k, self[k][index]
    def winnow(self, indices, invert = False):
        if invert:
            allIndices = np.arange(self.storedCount)
            indices = allIndices[np.in1d(allIndices, indices, invert = True)]
        length = len(indices)
        for key in self:
            subData = self[key]
            subData[:length] = subData[indices]
        self.storedCount = length
    def drop_duplicates(self, key = 0):
        self.winnow(np.unique(self[key], return_index = True)[1])
    def sort(self, key = 0):
        self.winnow(np.argsort(self[key]))
    def tidy(self):
        self.drop_duplicates()
        self.sort()
    def pop(self, index):
        toReturn = self.retrieve(index)
    def drop(self, index):
        indices = np.concatenate([
            np.arange(index),
            np.arange(index + 1, self.storedCount)
            ])
        self.winnow(indices)
    def index(self, val, key = 0):
        return np.argwhere(self[key] == val)[0][0]
    @property
    def nbytes(self):
        return sum(v.nbytes for v in self.values())
    @property
    def strnbytes(self):
        return prettify_nbytes(self.nbytes)

# def _producer_load_wrapper(func):
#     @wraps(func)
#     def wrapper(self, *args, process = False, **kwargs):
#         loaded = func(self, *args, **kwargs)
#         if process:
#             leftovers = self._load_process(loaded)
#             if len(leftovers):
#                 raise ProducerLoadFail(leftovers)
#             return
#         else:
#             return loaded
#     return wrapper

def _producer_update_outs(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
        # self._update_token()
        # return toReturn
    return wrapper

class Producer(Frame):

    def __init__(self,
            # baselines = dict(),
            _outVars = [],
            **kwargs
            ):

        self.outputKey = 'outputs'
        self.outVars = _outVars

        super().__init__(**kwargs)

    def out(self):
        for v in self.outVars:
            yield v.name, v.value

    @property
    def storages(self):
        try:
            return self.case.storages
        except AttributeError:
            self.case.storages = OrderedDict()
            return self.case.storages
    @property
    def storage(self):
        try:
            return self._storage
        except AttributeError:
            self.add_storage()
            return self._storage
    def _get_storage(self, key):
        try:
            storage = self.storages[key]
        except KeyError:
            keys, vals, types = zip(*(
                (v.name, v.value, v.dtype)
                    for v in self.outVars
                ))
            storage = Storage(keys, vals, types, key)
            self.storages[key] = storage
        return storage
    def add_storage(self, key = None):
        key = self.outputKey if key is None else key
        storage = self._get_storage(key)
        storeFn = storage.store
        self._store = lambda: storeFn(self.outVars)
        self._storage = storage
    def del_storage(self):
        del self._storage
        del self._store
    def store(self):
        try:
            self._store()
        except AttributeError:
            self.add_storage()
            self._store()
    def clear(self):
        self.storage.clear()
    @property
    @casemethod
    def nbytes(self):
        return sum([o.nbytes for o in self.storages.values()])
    @property
    @casemethod
    def strnbytes(self):
        return prettify_nbytes(self.nbytes)

    def _producer_prompt(self, prompter):
        self.store()

    @property
    def readouts(self):
        return self.reader.sub(self.outputKey)
    @property
    def writeouts(self):
        return self.writer.sub(self.outputKey)

    @disk.h5filewrap
    def save(self, silent = False, clear = True):
        try:
            self._save()
        except ProducerNothingToSave:
            if not silent:
                warnings.warn("No data was saved - did you expect this?")
        if clear:
            self.clear(silent = True)
    def _save(self):
        if not len(self.storage):
            raise ProducerNothingToSave
        self.writeouts.add(self, 'producer')
        for key, val in self.storage.items():
            wrapped = AnchorArray(val, extendable = True)
            self.writeouts.add(wrapped, key)
        # self.writeouts.add_dict(self.storage.collateral, 'collateral')

    def load(self, arg):
        self.process_loaded(self.load_out(arg))
    def load_out(self, arg):
        return self._load_out(arg)
    def _load_out(self, i):
        return self.load_stored(i)
    def load_stored(self, i):
        try:
            loaded = OrderedDict(self.storage.retrieve(i))
            loaded.name = self.storage.name
            return loaded
        except IndexError:
            raise LoadFail

    def process_loaded(self, loaded):
        leftovers = self._process_loaded(loaded)
        assert not len(leftovers)
    def _process_loaded(self, loaded):
        return loaded

    #
    # def _load_process(self, outs):
    #     return outs
    # @_producer_load_wrapper
    # def _load_raw(self, outs):
    #     if not outs.name == self.storage.name:
    #         raise ProducerLoadFail(
    #             "SubKeys misaligned:", (outs.name, self.storage.name)
    #             )
    #     return {**outs}
    # @_producer_load_wrapper
    # def _load_siblings(self, arg):
    #     for sibling in self.siblings:
    #         try:
    #             return sibling.load(arg, process = False)
    #         except LoadFail:
    #             pass
    #     raise LoadFail
    # @_producer_load_wrapper

    # @_producer_load_wrapper
    # def _load_index_disk(self, index):
    #     ks = self.storage.keys()
    #     return dict(zip(ks, (self.readouts[k][index] for k in ks)))
    # def _load_index(self, index, **kwargs):
    #     try:
    #         return self._load_index_stored(index, **kwargs)
    #     except IndexError:
    #         return self._load_index_disk(index, **kwargs)
    # def _load_out(self, arg, **kwargs):
    #     if isinstance(arg, dict):
    #         return self._load_raw(arg, **kwargs)
    #     else:
    #         try:
    #             return self._load_index(arg, **kwargs)
    #         except IndexError:
    #             raise ProducerLoadFail
    #         except TypeError:
    #             raise LoadFail
    # def load(self, arg, silent = False, process = True, **kwargs):
    #     try:
    #         return self._load(arg, process = process, **kwargs)
    #     except LoadFail as e:
    #         # try:
    #         #     return self._load_siblings(arg, **kwargs)
    #         # except LoadFail:
    #         if not silent:
    #             raise e
    #         else:
    #             return
