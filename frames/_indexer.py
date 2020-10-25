from functools import wraps
import weakref
from collections import OrderedDict, namedtuple
from collections.abc import Mapping, Sequence

import numpy as np

from h5anchor.reader import PathNotInFrameError
from h5anchor.anchor import NoActiveAnchorError
from funcy import Fn, Value

from ._producer import Producer, LoadFail, OutsNull

from ..exceptions import *
class IndexerException(EverestException):
    pass
class IndexAlreadyLoaded(IndexerException):
    pass
class IndexerNullVal(IndexerException):
    pass
class IndexerLoadFail(LoadFail, IndexerException):
    pass
class IndexerLoadNull(IndexerLoadFail, IndexerNullVal):
    pass
class IndexerLoadRedundant(IndexerLoadFail):
    pass
class NotIndexlike(TypeError, IndexerException):
    pass

class Indices(Mapping):

    def __init__(self, host):
        self._host = weakref.ref(host)
        super().__init__()

    @property
    def host(self):
        host = self._host()
        assert not host is None
        return host

    @property
    def indexers(self):
        return tuple([*self.host._indexers()][1:])
    @property
    def types(self):
        return tuple([*self.host._indexerTypes()][1:])
    def keys(self):
        return tuple([*self.host._indexerKeys()][1:])
    @property
    def asdict(self):
        return OrderedDict(zip(self.keys(), self.indexers))
    def items(self):
        return self.asdict.items()
    def values(self):
        return self.asdict.values()

    @property
    def info(self):
        return list(zip(
            self.indexers,
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
        if type(arg) is Value:
            arg = arg.value
        trueTypes = [issubclass(type(arg), t) for t in self.types]
        if any(trueTypes):
            return trueTypes.index(True)
        else:
            raise NotIndexlike(repr(arg)[:100], type(arg))
    def _get_indexInfo(self, arg):
        return self.info[self._get_metaIndex(arg)]
    def _process_index(self, arg):
        i, ik, it = self._get_indexInfo(arg)
        if arg < 0.:
            return i - arg
        else:
            return arg
    def process_endpoint(self, arg, close = False):
        i, ik, it = self._get_indexInfo(arg)
        if close:
            target = self
        else:
            target = None
        comp = Fn(target).get('indices', ik) >= self._process_index(arg)
        comp.index = arg
        return comp

    def nullify(self):
        for indexer in self.indexers:
            indexer.value = None
    def zero(self):
        for indexer in self.indexers:
            indexer.value = 0
    @property
    def isnull(self):
        return any([i.null for i in self.indexers])
    @property
    def iszero(self):
        if self.isnull:
            return False
        else:
            return any([i == 0 for i in self.indexers])
    @property
    def ispos(self):
        return not (self.isnull or self.iszero)

    @property
    def disk(self):
        diskIndices = OrderedDict()
        for k in self.keys():
            diskIndices[k] = list(self.host.readouts[k])
        return diskIndices
    @property
    def stored(self):
        storedIndices = OrderedDict()
        stored = dict(self.host.outs.zipstacked)
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
        stored = zip(*[self.host.outs.stored[k] for k in self.keys()])
        toDrop = []
        # print(list(clashes))
        # print(list(stored))
        for i, row in enumerate(stored):
            if any(all(r == c for r, c in zip(row, crow)) for crow in clashes):
                toDrop.append(i)
        self.host.outs.drop(toDrop)

    def out(self):
        outs = super(Indexer, self.host)._out()
        add = OrderedDict(zip(
            self.keys(),
            [OutsNull if i.null else i.value for i in self.indexers]
            ))
        outs.update(add)
        return outs

    def save(self):
        self.indices.drop_clashes()
        return super(Indexer, self.host)._save()

    def load_process(self, outs):
        outs = super(Indexer, self.host)._load_process(outs)
        vals = [outs.pop(k) for k in self.keys()]
        if any([v is OutsNull for v in vals]):
            raise IndexerLoadNull
        if vals == self:
            raise IndexerLoadRedundant(vals, self)
        for val, i in zip(vals, self.indexers):
            i.value = val
            assert i._value == val
        return outs

    def load(self, arg):
        if isinstance(arg, Fn) and hasattr(arg, 'index'):
            arg = arg.index
        try:
            i, ik, it = self._get_indexInfo(arg)
        except TypeError:
            return super(Indexer, self.host)._load(arg)
        arg = self._process_index(arg)
        try:
            ind = self.host.outs.index(**{ik: arg})
        except ValueError:
            try:
                ind = self.disk[ik].index(arg)
            except (ValueError, NoActiveAnchorError, PathNotInFrameError):
                raise IndexerLoadFail
            return self.host._load_index_disk(ind)
        return self.host._load_index_stored(ind)

    def __eq__(self, arg):
        return all(i == a for i, a in zip(self, arg))

    def __getitem__(self, key):
        return self.asdict[key]
    def __len__(self):
        return len(self.indexers)
    def __iter__(self):
        for i in range(len(self)):
            yield self.indexers[i]

    def __getattr__(self, key):
        try:
            return self.asdict[key]
        except KeyError:
            raise AttributeError

    def __repr__(self):
        keyvalstr = ', '.join('=='.join((k, str(v)))
            for k, v in self.asdict.items()
            )
        return 'Indices{' + keyvalstr + '}'

class Indexer(Producer):

    def __init__(self,
            **kwargs
            ):
        self._indices = None
        super().__init__(**kwargs)

    @property
    def indices(self):
        if self._indices is None:
            self._indices = Indices(self)
        return self._indices

    def _indexers(self):
        yield None
    def _indexerKeys(self):
        yield None
    def _indexerTypes(self):
        yield None

    def _out(self):
        return self.indices.out()
    def _save(self):
        return self.indices.save()
    def _load_process(self, outs):
        return self.indices.load_process(outs)
    def _load(self, arg):
        return self.indices.load(arg)
