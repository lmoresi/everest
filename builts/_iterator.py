import numpy as np
from types import FunctionType

from .. import disk
from ._counter import Counter
from ._cycler import Cycler
from ._producer import Producer
from ._producer import make_dataDict
from ._stampable import Stampable
from ..exceptions import EverestException

class LoadFail(EverestException):
    pass
class LoadDiskFail(EverestException):
    pass
class LoadStoredFail(EverestException):
    pass

class Bounce:
    def __init__(self, iterator, count):
        self.iterator = iterator
        self.count = count
    def __enter__(self):
        self.returnStep = self.iterator.count()
        self.iterator.store()
        self.iterator.load(self.count)
        return self.iterator
    def __exit__(self, *args):
        self.iterator.load(self.returnStep)

class Iterator(Counter, Cycler, Stampable):

    def __init__(
            self,
            **kwargs
            ):

        super().__init__(**kwargs)

        # Producer attributes:
        self._outFns.append(self._out)
        self.outkeys.extend(self._outkeys)
        self.samples.extend(
            [np.array([data,]) for data in self.out()]
            )
        self.indexKey = '_count_'
        self.dataKeys = [
            key for key in self.outkeys if not key == self.indexKey
            ]

        # Cycler attributes:
        self._cycle_fns.append(self.iterate)

        # Built attributes:
        self._post_anchor_fns.append(self._iterator_post_anchor)

        self.initialise()

    def _iterator_post_anchor(self):
        self.h5filename = self.writer.h5filename

    def initialise(self):
        self.count.value = 0
        self._initialise()

    def reset(self):
        self.initialise()

    def iterate(self, n = 1):
        for i in range(n):
            self.count += 1
            self._iterate()

    def load(self, count):
        if not self.count() == count:
            loadDict = self._load_dataDict(count)
            self._load(loadDict)
            self.count.value = count

    def _load_dataDict(self, count):
        try:
            return self._load_dataDict_stored(count)
        except LoadStoredFail:
            try:
                return self._load_dataDict_saved(count)
            except:
                raise LoadFail

    def _load_dataDict_stored(self, count):
        if not count in self.counts_stored:
            raise LoadStoredFail
        dataDict = self.make_dataDict()
        counts = dataDict[self.indexKey]
        index = np.where(counts == count)[0][0]
        datas = [dataDict[key] for key in self.dataKeys]
        return dict(zip(self.dataKeys, [data[index] for data in datas]))

    def _load_dataDict_saved(self, count):
        if not self.anchored:
            raise LoadDiskFail
        counts = self.reader[self.hashID, self.indexKey]
        matches = np.where(counts == count)[0]
        assert len(matches) <= 1
        if len(matches) == 0:
            print(matches)
            raise exceptions.CountNotOnDiskError
        else:
            index = matches[0]
        datas = [self.reader[self.hashID, key] for key in self.dataKeys]
        return dict(zip(self.dataKeys, [data[index] for data in datas]))

    def bounce(self, count):
        return Bounce(self, count)

from .examples import pimachine as example
