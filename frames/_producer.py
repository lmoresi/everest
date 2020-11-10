import numpy as np
import math
from functools import wraps
from collections.abc import Mapping
from collections import OrderedDict
import warnings
import time

import wordhash
from h5anchor import Reader, Writer, disk
from h5anchor.array import AnchorArray
# import reseed

from . import Frame
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
        filteredkeys = list()
        for k, v, t in zip(keys, vals, types):
            if not t is None:
                shape = v.shape if isinstance(v, np.ndarray) else ()
                storedList.append(np.empty((blocklen, *shape), t))
                filteredkeys.append(k)
        self.storedList = storedList
        self.stored = OrderedDict(zip(filteredkeys, self.storedList))
        self.keys = self.stored.keys
        self.masterKey = list(self.keys())[0]
        self.blocklen = blocklen
        self.storedCount = 0
        self.name = name
    def store(self, outs):
        for k, v in outs:
            if not k is None:
                try:
                    self.stored[k][self.storedCount] = v
                except KeyError:
                    dtype, shape = _get_data_properties(v)
                    self.stored[k] = np.empty((self.blocklen, *shape), dtype)
                    self.stored[k][self.storedCount] = v
                except IndexError:
                    raise NotYetImplemented
        self.storedCount += 1
    def __len__(self):
        return self.storedCount
    def __getitem__(self, key):
        try:
            return self.stored[key][:self.storedCount]
        except KeyError:
            return self.storedList[key][:self.storedCount]
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
            indices = allIndices[~np.in1d(allIndices, indices)]
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

def _producer_load_wrapper(func):
    @wraps(func)
    def wrapper(self, *args, process = False, **kwargs):
        loaded = func(self, *args, **kwargs)
        if process:
            leftovers = self._load_process(loaded)
            if len(leftovers):
                raise ProducerLoadFail(leftovers)
            return
        else:
            return loaded
    return wrapper

def _producer_update_outs(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
        # self._update_token()
        # return toReturn
    return wrapper

class Producer(Frame):

    def __init__(self,
            baselines = dict(),
            **kwargs
            ):

        self.outputKey = 'outputs'

        super().__init__(**kwargs)

        # self.baselines = dict()
        # for key, val in sorted(baselines.items()):
        #     self.baselines[key] = AnchorArray(val, extendable = False)

        # super().__init__(baselines = self.baselines, **kwargs)


    #     self._producer_token = 0
    #
    # def _update_token(self):
    #     self._producer_token += 1

    # @property
    # def outputMasterKey(self):
    #     return '/'.join([k for k in self._outputMasterKey() if len(k)])
    # def _outputMasterKey(self):
    #     yield 'outputs'
    # @property
    # def outputSubKey(self):
    #     sk = '/'.join([k for k in self._outputSubKey() if len(k)])
    #     if not len(sk):
    #         sk = self._defaultOutputSubKey
    #     return sk
    # def _outputSubKey(self):
    #     yield ''
    # @property
    # def outputKey(self):
    #     keys = [self.outputMasterKey, self.outputSubKey]
    #     return '/'.join([k for k in keys if len(k)])

    def _out_keys(self):
        yield None
    def _out_vals(self):
        yield None
    def _out_types(self):
        yield None
    def out(self):
        for k, v in zip(self._out_keys(), self._out_vals()):
            if not k is None:
                yield k, v
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
            storage = self.storages[self.outputKey]
        except KeyError:
            storage = Storage(
                self._out_keys(),
                self._out_vals(),
                self._out_types(),
                self.outputKey
                )
            self.storages[self.outputKey] = storage
        return storage

    def store(self, silent = False):
        self._store(silent = silent)
    def _store(self, silent = False):
        self.storage.store(self.out())
    def clear(self, silent = False):
        self._clear(silent = silent)
    def _clear(self, silent = False):
        self.storage.clear(silent = silent)
    @property
    def nbytes(self):
        return sum([o.nbytes for o in self.storages.values()])
    @property
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

    def _load_process(self, outs):
        return outs
    @_producer_load_wrapper
    def _load_raw(self, outs):
        if not outs.name == self.storage.name:
            raise ProducerLoadFail(
                "SubKeys misaligned:", (outs.name, self.storage.name)
                )
        return {**outs}
    # @_producer_load_wrapper
    # def _load_siblings(self, arg):
    #     for sibling in self.siblings:
    #         try:
    #             return sibling.load(arg, process = False)
    #         except LoadFail:
    #             pass
    #     raise LoadFail
    @_producer_load_wrapper
    def _load_index_stored(self, index):
        return OrderedDict(self.storage.retrieve(index))
    @_producer_load_wrapper
    def _load_index_disk(self, index):
        ks = self.storage.keys()
        return dict(zip(ks, (self.readouts[k][index] for k in ks)))
    def _load_index(self, index, **kwargs):
        try:
            return self._load_index_stored(index, **kwargs)
        except IndexError:
            return self._load_index_disk(index, **kwargs)
    def _load(self, arg, **kwargs):
        if isinstance(arg, dict):
            return self._load_raw(arg, **kwargs)
        else:
            try:
                return self._load_index(arg, **kwargs)
            except IndexError:
                raise ProducerLoadFail
            except TypeError:
                raise LoadFail
    def load(self, arg, silent = False, process = True, **kwargs):
        try:
            return self._load(arg, process = process, **kwargs)
        except LoadFail as e:
            # try:
            #     return self._load_siblings(arg, **kwargs)
            # except LoadFail:
            if not silent:
                raise e
            else:
                return
