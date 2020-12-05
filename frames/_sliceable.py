from collections.abc import Iterator

from ptolemaic import Case

from . import Frame
from ..exceptions import *

class LeftoverException(EverestException, ValueError):
    pass

class EllipsisIterable(Iterator):
    def __iter__(self):
        return self
    def __next__(self):
        return Ellipsis

# class SliceableCase(Case):
#     def __getitem__(case, args, /):
#         frame = case.frame
#         leftovers = frame._master_setitem(..., args)
#         newargs = list(v for _, v in leftovers)
#         print(newargs)
#         return frame.__getitem__(newargs)

class Sliceable(Frame):

    # @classmethod
    # def _frameClasses(cls):
    #     d = super()._frameClasses()
    #     d['Case'][0].insert(0, SliceableCase)
    #     return d

    def __setitem__(self, keys, vals):
        leftovers = self._master_setitem(keys, vals)
        try:
            _ = next(leftovers)
            raise LeftoverException
        except StopIteration:
            pass
    def _master_setitem(self, keys, vals):
        keys = EllipsisIterable() if keys is Ellipsis else keys
        keyvals = zip(keys, vals)
        try:
            self._setitem(keyvals)
        except StopIteration:
            pass
        return keyvals
    def _setitem(self, keyvals, /):
        pass

    def __getitem__(self, keys):
        leftovers, vals = self._master_getitem(keys)
        try:
            _ = next(leftovers)
            raise LeftoverException
        except StopIteration:
            if len(vals) == 1:
                return vals[0]
            else:
                return vals
    def _master_getitem(self, keys):
        if keys is Ellipsis:
            keys = EllipsisIterable()
        else:
            try:
                keys = iter(keys)
            except TypeError:
                keys = iter((keys,))
        vals = list()
        try:
            self._getitem(keys, vals)
        except StopIteration:
            pass
        return keys, vals
    def _getitem(self, keys, outs):
        pass
