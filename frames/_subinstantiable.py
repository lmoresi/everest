from collections import OrderedDict

from . import Frame

class SubInstantiable(Frame):
    def __init__(self,
            _subInstantiators = OrderedDict()
            **kwargs,
            ):
        self._subInstantiators = _subInstantiators
        super().__init__(**kwargs)
    def __setitem__(self, keys, vals):
        for key, val, si in zip(keys, vals, self._subInstantiators.values()):
            si[key] = val
        self._subInstantiable_change_state_hook()
    def _subInstantiable_change_state_hook(self):
        pass
    def _vector(self):
        for pair in super()._vector(): yield pair
        for pair in self._subInstantiators.items(): yield pair
