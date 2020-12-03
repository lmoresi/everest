from collections import OrderedDict

from ._settable import Settable
from ..utilities import ordered_unpack

class SubInstantiable(Settable):
    def __init__(self,
            _subInstantiators = OrderedDict(),
            **kwargs,
            ):
        self._subInstantiators = _subInstantiators
        super().__init__(**kwargs)
        self._subInstantiable_change_state_hook()
    def _subInstantiable_change_state_hook(self):
        pass
    def _vector(self):
        for pair in super()._vector(): yield pair
        for pair in self._subInstantiators.items(): yield pair
    def _setitem(self, keyvals, /):
        super()._setitem(keyvals)
        for sub in self._subInstantiators.values():
            k, v = next(keyvals)
            sub[k] = v
