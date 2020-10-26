import numpy as np

from funcy import Function

from ._indexer import Indexer

class Counter(Indexer):

    _defaultCountsKey = 'count'

    def __init__(self, **kwargs):
        self._countsKey = self._defaultCountsKey
        self._count = Function(
            np.int32,
            name = self._countsKey,
            )
        super().__init__(**kwargs)

    def _indexers(self):
        for o in super()._indexers(): yield o
        yield self._count
    def _indexerKeys(self):
        for o in super()._indexerKeys(): yield o
        yield self._countsKey
    def _indexerTypes(self):
        for o in super()._indexerTypes(): yield o
        yield (int, np.integer, np.int)
