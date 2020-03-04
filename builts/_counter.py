import numpy as np

from ._producer import Producer
from ._producer import AbortStore
from ..value import Value

class Counter(Producer):

    def __init__(self, **kwargs):
        self.count = Value(0)
        self.counts = []
        self.counts_stored = []
        self.indexKey = 'count'
        super().__init__(**kwargs)
        # Producer attributes:
        self._outFns.append(self.countoutFn)
        self.outkeys.append('count')
        self._pre_store_fns.append(self._counter_pre_store_fn)
        self._post_store_fns.append(self._counter_post_store_fn)
        self._pre_save_fns.append(self._counter_pre_save_fn)
        self._post_save_fns.append(self._counter_post_save_fn)
        # Built attributes:
        self._post_anchor_fns.append(self._update_counts)

    def countoutFn(self):
        yield np.array(self.count(), dtype = np.int32)

    def _counter_pre_store_fn(self):
        if self.count() in self.counts: raise AbortStore

    def _counter_post_store_fn(self):
        self.counts.append(self.count())
        self.counts_stored.append(self.count())

    def _counter_pre_save_fn(self):
        self.counts = self._get_disk_counts()
        processed = []
        for row in self.stored:
            count = int(dict(zip(self.outkeys, row))[self.indexKey])
            if not count in self.counts:
                processed.append(row)
                self.counts.append(count)
        self.stored = processed

    def _counter_post_save_fn(self):
        self.counts_stored = []

    def _get_disk_counts(self):
        try:
            counts = list(set(self.reader(
                self.hashID, 'outputs', 'count'
                )))
            counts = [int(x) for x in counts]
            return counts
        except KeyError: return []

    def _update_counts(self):
        self.counts.extend(self._get_disk_counts())
        self.counts = sorted(set(self.counts))