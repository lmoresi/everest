from functools import wraps
from collections import OrderedDict, namedtuple
from collections.abc import Mapping, Sequence
import numbers

import numpy as np

from h5anchor.reader import PathNotInFrameError
from h5anchor.anchor import NoActiveAnchorError
from funcy import Fn
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

class Indices(Mapping, Hosted):

    def __init__(self, host):
        super().__init__(host)

    @property
    def types(self):
        return tuple(self.frame._indexerTypes())

    @property
    def master(self):
        return list(self.values())[0]

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
    def disk(self):
        diskIndices = OrderedDict()
        for k in self.keys():
            diskIndices[k] = list(self.frame.readouts[k])
        return diskIndices
    @property
    def stored(self):
        storedIndices = OrderedDict()
        stored = dict(self.frame.outs.zipstacked)
        for k in self.keys():
            storedIndices[k] = list(stored[k])
        return storedIndices
    @property
    def all(self):
        return self._all()
    def _all(self, clashes = False):
        combinedIndices = OrderedDict()
        try:
            diskIndices = self.disk
        except (NoActiveAnchorError, PathNotInFrameError):
            diskIndices = OrderedDict([k, []] for k in self.keys())
        storedIndices = self.stored
        for k in self.keys():
            combinedIndices[k] = sorted(set(
                [*diskIndices[k], *storedIndices[k]]
                ))
        if clashes:
            clashes = OrderedDict()
            for k in self.keys():
                clashes[k] = sorted(set.intersection(
                    set(diskIndices[k]), set(storedIndices[k])
                    ))
            return combinedIndices, clashes
        else:
            return combinedIndices
    def drop_clashes(self):
        _, clashes = self._all(clashes = True)
        clashes = zip(*clashes.values())
        stored = zip(*[self.frame.outs.stored[k] for k in self.keys()])
        toDrop = []
        # print(list(clashes))
        # print(list(stored))
        for i, row in enumerate(stored):
            if any(all(r == c for r, c in zip(row, crow)) for crow in clashes):
                toDrop.append(i)
        self.frame.outs.drop(toDrop)

    def out(self):
        outs = super(Indexable, self.frame)._out()
        add = OrderedDict(zip(
            self.keys(),
            [OutsNull if i.null else i.value for i in self.values()]
            ))
        outs.update(add)
        return outs

    def save(self):
        self.drop_clashes()
        return super(Indexable, self.frame)._save()

    def load_process(self, outs):
        outs = super(Indexable, self.frame)._load_process(outs)
        vals = [outs.pop(k) for k in self.keys()]
        if any([v is OutsNull for v in vals]):
            raise IndexableLoadNull
        if vals == self:
            raise IndexableLoadRedundant(vals, self)
        for val, i in zip(vals, self.values()):
            i.value = val
        return outs

    def load(self, arg, **kwargs):
        if isinstance(arg, Fn) and hasattr(arg, 'index'):
            arg = arg.index
        try:
            i, ik, it = self.get_indexInfo(arg)
        except TypeError:
            return super(Indexable, self.frame)._load(arg, **kwargs)
        try:
            ind = self.frame.outs.index(**{ik: arg})
        except ValueError:
            try:
                ind = self.disk[ik].index(arg)
            except (ValueError, NoActiveAnchorError, PathNotInFrameError):
                raise IndexableLoadFail
            return self.frame._load_index_disk(ind, **kwargs)
        return self.frame._load_index_stored(ind, **kwargs)

    def __eq__(self, arg):
        if isinstance(arg, type(self)):
            arg = arg.values()
        return all(i == a for i, a in zip(self.values(), arg))

    def __getitem__(self, i):
        if type(i) is str:
            i = list(self.frame._indexerKeys()).index(i)
        return list(self.frame._indexers())[i]
    def __len__(self):
        return len(tuple(self.frame._indexerKeys()))
    def __iter__(self):
        return self.frame._indexerKeys()
    def __setitem__(self, key, arg):
        self[key].value = arg

    def __repr__(self):
        keyvalstr = ', '.join('=='.join((k, str(v)))
            for k, v in self.items()
            )
        return 'Indices{' + keyvalstr + '}'
    @property
    def hashID(self):
        return wordhash.w_hash(repr(self))

class Indexable(Producer):

    _defaultCountsKey = 'count'

    def __init__(self,
            **kwargs
            ):
        self._indices = None
        self._countsKey = self._defaultCountsKey
        self._count = Fn(
            np.int32,
            name = self._countsKey,
            )
        super().__init__(**kwargs)

    def _vector(self):
        for pair in super()._vector(): yield pair
        yield ('count', self.indices)

    @property
    def indices(self):
        if self._indices is None:
            self._indices = Indices(self)
        return self._indices

    def _indexers(self):
        yield self._count
    def _indexerKeys(self):
        yield self._countsKey
    def _indexerTypes(self):
        yield numbers.Integral

    def _out(self):
        return self.indices.out()
    def _save(self):
        return self.indices.save()
    def _load_process(self, outs):
        return self.indices.load_process(outs)
    def _load(self, arg, **kwargs):
        return self.indices.load(arg, **kwargs)
