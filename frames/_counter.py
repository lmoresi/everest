import numpy as np

from funcy import Function

from ._indexer import Indexer

class Counter(Indexer):

    _defaultCountsKey = 'count'
    _defaultCountNullVal = -999999999

    def __init__(self, **kwargs):
        self._countNullVal = self._defaultCountNullVal
        self._countsKey = self._defaultCountsKey
        self._count = Function(
            self._countNullVal,
            initial = 'null',
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
