import numbers
import numpy as np

from funcy import Function

from ._indexable import Indexable

class Chronable(Indexable):

    _defaultChronsKey = 'chron'
    _defaultChronNullVal = float('nan')

    def __init__(self, **kwargs):
        self._chronsKey = self._defaultChronsKey
        self._chron = Function(
            np.float32,
            name = self._chronsKey,
            )
        super().__init__(**kwargs)

    def _indexers(self):
        for o in super()._indexers(): yield o
        yield self._chron
    def _indexerKeys(self):
        for o in super()._indexerKeys(): yield o
        yield self._chronsKey
    def _indexerTypes(self):
        for o in super()._indexerTypes(): yield o
        yield numbers.Real
