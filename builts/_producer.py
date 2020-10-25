import numpy as np
from functools import wraps
from collections.abc import Mapping
from collections import OrderedDict
import warnings

import wordhash

from .. import disk
from ..reader import Reader
from ..writer import Writer

# from . import buffersize_exceeded
# from ._promptable import Promptable
from . import Built
from ..array import AnchorArray
from .. import exceptions
from ..utilities import Grouper, prettify_nbytes

class ProducerException(exceptions.EverestException):
    pass
class ProducerNoOuts(ProducerException):
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
# class ProducerMissingMethod(exceptions.MissingMethod):
#     pass

from collections import OrderedDict
import numpy as np
import math

from everest.utilities import make_hash
from everest.builts._producer import ProducerException

class OutsException(ProducerException):
    pass
class OutsAlreadyStored(OutsException):
    pass
class OutsAlreadyCleared(OutsException):
    pass
class NullValueDetected(OutsException):
    pass
class OutsNull:
    pass

class Outs:
    def __init__(self, keys, name = 'default'):
        self._keys, self.name = keys, name
        self._data = OrderedDict([(k, OutsNull) for k in self._keys])
        self._collateral = OrderedDict()
        self._data.name = name
        self.stored = OrderedDict([(k, []) for k in self._keys])
        self.hashVals = []
        self.token = None
    @property
    def data(self):
        if any([v is OutsNull for v in self._data.values()]):
            raise NullValueDetected
        else:
            return self._data
    @property
    def collateral(self):
        return self._collateral
    def update(self, outs, silent = False):
        if any([v is OutsNull for v in outs.values()]):
            if not silent:
                raise NullValueDetected
        for k, v in outs.items():
            self[k] = v
    def __setitem__(self, k, v):
        if k in self._keys:
            self._data[k] = v
            setattr(self, k, v)
        else:
            raise OutsKeysImmutable
    def __getitem__(self, k):
        return self._data[k]
    def __delitem__(self, k):
        raise OutsKeysImmutable
    def store(self, silent = False):
        hashVal = make_hash(self._data.values())
        if hashVal in self.hashVals:
            if not silent:
                warnings.warn(
                    "This data was already saved - did you expect this?"
                    )
        else:
            if any([v is OutsNull for v in self._data.values()]):
                if silent:
                    pass
                else:
                    raise NullValueDetected
            else:
                for k, v in self._data.items():
                    self.stored[k].append(v)
                self.hashVals.append(hashVal)
    def sort(self, key = None):
        if key is None:
            key = self._keys[0]
        sortInds = np.stack(self.stored[key]).argsort()
        for k, v in self.zipstacked:
            self.stored[k][:] = v[sortInds]
    def clear(self, silent = False):
        if not silent:
            if not len(self.hashVals):
                warnings.warn("No data was cleared - did you expect this?")
        self.hashVals.clear()
        for k, v in self.stored.items():
            v.clear()
    def retrieve(self, index):
        for v in self.stored.values():
            yield v[index]
    def pop(self, index):
        _ = self.hashVals.pop(index)
        for v in self.stored.values():
            yield v.pop(index)
    def drop(self, indices):
        keep = [i for i in range(len(self)) if not i in indices]
        self.hashVals[:] = [self.hashVals[i] for i in keep]
        for v in self.stored.values():
            v[:] = [v[i] for i in keep]
    def index(self, **kwargs):
        search = lambda k, v: self.stored[k].index(v)
        indices = [search(k, v) for k, v in sorted(kwargs.items())]
        if len(set(indices)) != 1:
            raise ValueError
        return indices[0]
    def keys(self):
        return self._data.keys()
    @property
    def stacked(self):
        if len(self):
            for v in self.stored.values():
                assert len(v)
                yield np.stack(v)
        else:
            for v in self.stored:
                yield []
    @property
    def zipstacked(self):
        return zip(self._keys, self.stacked)
    @property
    def nbytes(self):
        nbytes = np.array(self.hashVals).nbytes
        for v in self.stored.values():
            nbytes += np.array(v).nbytes
        return nbytes
    @property
    def strnbytes(self):
        return prettify_nbytes(self.nbytes)
    def __len__(self):
        return len(self.hashVals)

def _producer_load_wrapper(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        loaded = func(self, *args, **kwargs)
        leftovers = self._load_process(loaded)
        if len(leftovers):
            raise ProducerLoadFail(leftovers)
    return wrapper

def _producer_update_outs(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        toReturn = func(self, *args, **kwargs)
        self._update_randomstate()
        return toReturn
    return wrapper

class Producer(Built):

    _defaultOutputSubKey = 'default'

    def __init__(self,
            baselines = dict(),
            **kwargs
            ):

        self.baselines = dict()
        for key, val in sorted(baselines.items()):
            self.baselines[key] = AnchorArray(val, extendable = False)

        self._outs = OrderedDict()
        self._randomstate = None

        super().__init__(baselines = self.baselines, **kwargs)

        self._update_randomstate()

    def _update_randomstate(self):
        print(wordhash.randint)
        self._randomstate = wordhash.randint(18)
    @property
    def randomstate(self):
        return self._randomstate

    @property
    def outputMasterKey(self):
        return '/'.join([k for k in self._outputMasterKey() if len(k)])
    def _outputMasterKey(self):
        yield 'outputs'
    @property
    def outputSubKey(self):
        sk = '/'.join([k for k in self._outputSubKey() if len(k)])
        if not len(sk):
            sk = self._defaultOutputSubKey
        return sk
    def _outputSubKey(self):
        yield ''
    @property
    def outputKey(self):
        keys = [self.outputMasterKey, self.outputSubKey]
        return '/'.join([k for k in keys if len(k)])

    @property
    def outs(self):
        sk = self.outputSubKey
        if sk in self._outs:
            outs = self._outs[sk]
            if self.randomstate != outs.token:
                outs.update(self.out())
                outs.token = self.randomstate
        else:
            outsDict = self.out()
            outs = Outs(outsDict.keys(), sk)
            self._outs[sk] = outs
            try:
                outs.update(outsDict)
            except NullValueDetected:
                pass
        return outs
    def _out(self):
        return OrderedDict()
    def out(self):
        return self._out()

    def store(self, silent = False):
        self._store(silent = silent)
    def _store(self, silent = False):
        self.outs.store(silent = silent)
    def clear(self, silent = False):
        self._clear(silent = silent)
    def _clear(self, silent = False):
        self.outs.clear(silent = silent)
    @property
    def nbytes(self):
        return sum([o.nbytes for o in self._outs.values()])
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
        if not len(self.outs):
            raise ProducerNothingToSave
        self.writeouts.add(self, 'producer')
        for key, val in self.outs.zipstacked:
            wrapped = AnchorArray(val, extendable = True)
            self.writeouts.add(wrapped, key)
        self.writeouts.add_dict(self.outs.collateral, 'collateral')

    def _load_process(self, outs):
        return outs
    @_producer_load_wrapper
    def _load_raw(self, outs):
        try:
            outsKey = outs.name
        except AttributeError:
            outsKey = self._defaultOutputSubKey
        if not outsKey == self.outputSubKey:
            raise ProducerLoadFail(
                "SubKeys misaligned:", (outsKey, self.outputSubKey)
                )
        return {**outs}
    @_producer_load_wrapper
    def _load_index_stored(self, index):
        return dict(zip(self.outs.keys(), self.outs.retrieve(index)))
    @_producer_load_wrapper
    def _load_index_disk(self, index):
        ks = self.outs.keys()
        return dict(zip(ks, (self.readouts[k][index] for k in ks)))
    def _load_index(self, index):
        try:
            return self._load_index_stored(index)
        except IndexError:
            return self._load_index_disk(index)
    def _load(self, arg):
        try:
            return self._load_raw(arg)
        except TypeError:
            try:
                return self._load_index(arg)
            except IndexError:
                raise ProducerLoadFail
            except TypeError:
                raise LoadFail
    def load(self, arg, silent = False):
        fn = lambda: self._load(arg)
        if silent:
            try: return fn()
            except LoadFail: pass
        return fn()
