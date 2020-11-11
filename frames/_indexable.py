from functools import wraps
from collections import OrderedDict, namedtuple
from collections.abc import Mapping, Sequence
import numbers

import numpy as np

from h5anchor.reader import PathNotInFrameError
from h5anchor.anchor import NoActiveAnchorError
from funcy import Fn, MutableVariable
from funcy import exceptions as funcyex
import wordhash

from ..utilities import make_scalar
from ..hosted import Hosted
from ._producer import Producer, LoadFail, OutsNull

from ..exceptions import *
class IndexableException(EverestException):
    pass
class IndexAlreadyLoaded(IndexableException):
    pass
class IndexableNullVal(IndexableException):
    pass
class IndexableLoadFail(LoadFail, IndexableException):
    pass
class IndexableLoadNull(IndexableLoadFail, IndexableNullVal):
    pass
class IndexableLoadRedundant(IndexableLoadFail):
    pass
class NotIndexlike(TypeError, IndexableException):
    pass

class IndexVar(MutableVariable):
    def __init__(self, *args, compType = numbers.Number, **kwargs):
        self.compType = compType
        super().__init__(*args, **kwargs)

class FrameIndices(Mapping, Hosted):

    def __init__(self, host, indexers):
        self.indexers = indexers
        self._indexerDict = OrderedDict(
            zip((i.name for i in self.indexers), self.indexers)
            )
        self._length = len(self.indexers)
        self.master = indexers[0]
        self.types = tuple(i.compType for i in indexers)
        super().__init__(host)

    @property
    def info(self):
        return list(zip(
            self.values(),
            self.keys(),
            self.types,
            ))
    def _check_indexlike(self, arg):
        try:
            _ = self._get_metaIndex(arg)
            return True
        except NotIndexlike:
            return False
    def _get_metaIndex(self, arg):
        # if isinstance(arg, Fn):
        #     try:
        #         arg = arg.value
        #     except funcyex.EvaluationError:
        #         raise NotIndexlike
        try:
            arg = make_scalar(arg)
        except ValueError:
            raise NotIndexlike
        trueTypes = [issubclass(type(arg), t) for t in self.types]
        if any(trueTypes):
            return trueTypes.index(True)
        else:
            raise NotIndexlike(repr(arg)[:100], type(arg))
    def get_indexInfo(self, arg):
        return self.info[self._get_metaIndex(arg)]
    def get_index(self, arg):
        return tuple(self.values())[self._get_metaIndex(arg)]
    def get_now(self, op = None):
        fn = Fn().get('indices').get[list(self.keys())[0]]
        if self.isnull:
            val = 0
        else:
            val = self.master.value
        if op is None:
            return fn, val
        else:
            return Fn(fn, val).op(op)
    # def _process_index(self, arg):
    #     i, ik, it = self.get_indexInfo(arg)
    #     if arg < 0.:
    #         return i - arg
    #     else:
    #         return arg

    def nullify(self):
        for k in self.keys(): self[k] = None
    def zero(self):
        for k in self.keys(): self[k] = 0
    @property
    def isnull(self):
        return any([i.null for i in self.values()])
    @property
    def iszero(self):
        if self.isnull:
            return False
        else:
            return any([i == 0 for i in self.values()])
    @property
    def ispos(self):
        return not (self.isnull or self.iszero)

    @property
    def disk(self, key = None):
        if key is None:
            for k in self: yield k, self.frame.readouts[k]
        else:
            return self.frame.readouts[key]
    @property
    def stored(self, key = None):
        if key is None:
            for k in self: yield k, self.frame.storage[k]
        else:
            return self.frame.storage[k]
    @property
    def captured(self):
        return self._all()
    # def _all(self, clashes = False):
    #     combinedIndices = OrderedDict()
    #     try:
    #         diskIndices = self.disk
    #     except (NoActiveAnchorError, PathNotInFrameError):
    #         diskIndices = OrderedDict([k, []] for k in self.keys())
    #     storedIndices = self.stored
    #     for k in self.keys():
    #         combinedIndices[k] = sorted(set(
    #             [*diskIndices[k], *storedIndices[k]]
    #             ))
    #     if clashes:
    #         clashes = OrderedDict()
    #         for k in self.keys():
    #             clashes[k] = sorted(set.intersection(
    #                 set(diskIndices[k]), set(storedIndices[k])
    #                 ))
    #         return combinedIndices, clashes
    #     else:
    #         return combinedIndices
    # def drop_clashes(self):
    #     _, clashes = self._all(clashes = True)
    #     clashes = zip(*clashes.values())
    #     stored = zip(*[self.frame.storage.stored[k] for k in self.keys()])
    #     toDrop = []
    #     # print(list(clashes))
    #     # print(list(stored))
    #     for i, row in enumerate(stored):
    #         if any(all(r == c for r, c in zip(row, crow)) for crow in clashes):
    #             toDrop.append(i)
    #     self.frame.storage.drop(toDrop)

    # def out(self):
    #     outs = super(Indexable, self.frame)._out()
    #     add = OrderedDict(zip(
    #         self.keys(),
    #         [OutsNull if i.null else i.value for i in self.values()]
    #         ))
    #     outs.update(add)
    #     return outs

    # def save(self):
    #     raise NotYetImplemented
    #     self.drop_clashes()
    #     return super(Indexable, self.frame)._save()

    # def load_process(self, outs):
    #     outs = super(Indexable, self.frame)._load_process(outs)
    #     vals = [outs.pop(k) for k in self.keys()]
    #     if any([v is OutsNull for v in vals]):
    #         raise IndexableLoadNull
    #     if vals == self:
    #         raise IndexableLoadRedundant(vals, self)
    #     for val, i in zip(vals, self.values()):
    #         i.value = val
    #     return outs
    #
    # def load(self, arg, **kwargs):
    #     if isinstance(arg, Fn) and hasattr(arg, 'index'):
    #         arg = arg.index
    #     try:
    #         i, ik, it = self.get_indexInfo(arg)
    #     except TypeError:
    #         return super(Indexable, self.frame)._load(arg, **kwargs)
    #     try:
    #         ind = self.frame.storage.index(arg, key = ik)
    #     except ValueError:
    #         try:
    #             ind = np.argwhere(self.disk[ik] == arg)[0][0]
    #         except (ValueError, NoActiveAnchorError, PathNotInFrameError):
    #             raise IndexableLoadFail
    #         return self.frame._load_index_disk(ind, **kwargs)
    #     return self.frame._load_index_stored(ind, **kwargs)

    def __eq__(self, arg):
        if isinstance(arg, type(self)):
            arg = arg.values()
        return all(i == a for i, a in zip(self.values(), arg))

    def __getitem__(self, key):
        try: return self._indexerDict[key]
        except KeyError: pass
        try: return self.indexers[key]
        except (TypeError, IndexError): pass
        raise KeyError
    def __len__(self):
        return self._length
    def __iter__(self):
        return iter(self._indexerDict)
    def __setitem__(self, key, arg):
        self[key].value = arg

    def __repr__(self):
        rows = [k + ': ' + str(v.data) for k, v in self.items()]
        keyvalstr = ',\n    '.join(rows)
        return type(self).__name__ + '{\n    ' + keyvalstr + ',\n    }'
    @property
    def hashID(self):
        return wordhash.w_hash(repr(self))

class Indexable(Producer):

    def __init__(self,
            _indices = [],
            _outVars = [],
            **kwargs
            ):
        var = IndexVar(
            np.int32,
            compType = numbers.Integral,
            name = 'count',
            )
        self.indices = FrameIndices(self, [var, *_indices])
        _outVars = [*self.indices.values(), *_outVars]
        super().__init__(_outVars = _outVars, **kwargs)

    def _vector(self):
        for pair in super()._vector(): yield pair
        yield ('count', self.indices)

    def _load_out(self, arg):
        try: return self.load_index(arg)
        except LoadFail: return super()._load_out(arg)
    def load_index(self, arg):
        try: indexVar = self.indices.get_index(arg)
        except NotIndexlike: raise LoadFail
        try: index = self.storage.index(arg, indexVar.name)
        except (KeyError, IndexError): raise LoadFail
        return self.load_stored(index)
    def _process_loaded(self, loaded):
        for key in self.indices:
            self.indices[key].value = loaded.pop(key)
        return super()._process_loaded(loaded)

    # def _save(self):
    #     return self.indices.save()
    # def _load_process(self, outs):
    #     return self.indices.load_process(outs)
    # def _load(self, arg, **kwargs):
    #     return self.indices.load(arg, **kwargs)
