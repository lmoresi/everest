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
            name = 'default',
            blocklen = int(1e6)
            ):
        self.stored = OrderedDict()
        self.keys = self.stored.keys
        self.blocklen = blocklen
        self.storedCount = 0
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
        return self.stored[key][:self.storedCount]
    def __iter__(self):
        return iter(self.keys())
    def clear(self, silent = False):
        self.storedCount = 0
    def retrieve(self, index):
        for k in self:
            yield self[k][index]
    def sort(self, key = None):
        raise NotYetImplemented
        # if not key is None:
        #     # key = list(self.keys())[0]
        #     raise NotYetImplemented
        # sortInds = np.stack([self.values()][0]).argsort()
        # for k, v in self.zipstacked:
        #     self.stored[k][:] = v[sortInds]
    def pop(self, index):
        raise NotYetImplemented
        # for v in self.stored.values():
        #     yield v.pop(index)
    def drop(self, indices):
        raise NotYetImplemented
        # keep = [i for i in range(len(self)) if not i in indices]
        # for v in self.stored.values():
        #     v[:] = [v[i] for i in keep]
    def index(self, **kwargs):
        raise NotYetImplemented
        # search = lambda k, v: self.stored[k].index(v)
        # indices = [search(k, v) for k, v in sorted(kwargs.items())]
        # if len(set(indices)) != 1:
        #     raise ValueError
        # return indices[0]
    @property
    def stacked(self):
        raise NotYetImplemented
        # if len(self):
        #     for v in self.stored.values():
        #         assert len(v)
        #         yield np.stack(v)
        # else:
        #     for v in self.stored:
        #         yield []
    @property
    def zipstacked(self):
        raise NotYetImplemented
        # return zip(self.keys(), self.stacked)
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
            storage = Storage(self._out_keys(), self.outputKey)
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
        for key, val in self.storage.zipstacked:
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
        return dict(zip(self.storage.keys(), self.storage.retrieve(index)))
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
