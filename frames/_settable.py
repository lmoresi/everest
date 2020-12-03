from collections.abc import Iterator

from . import Frame
from ..exceptions import *

class LeftoverSetArgs(EverestException, ValueError):
    pass

class EllipsisIterable(Iterator):
    def __iter__(self):
        return self
    def __next__(self):
        return Ellipsis

class Settable(Frame):
    def __setitem__(self, keys, vals):
        keys = EllipsisIterable() if keys is Ellipsis else keys
        keyvals = zip(keys, vals)
        try:
            self._setitem(keyvals)
        except StopIteration:
            pass
        try:
            kv = next(keyvals)
            raise LeftoverSetArgs
        except StopIteration:
            pass
    def _setitem(self, keyvals, /):
        pass
