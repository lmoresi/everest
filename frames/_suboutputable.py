from ._producer import Producer
from ._subinstantiable import SubInstantiable

class SubOutputable(SubInstantiable, Producer):
    def __init__(self,
            **kwargs,
            ):
        super().__init__(**kwargs)
    def _subInstantiable_change_state_hook(self):
        super()._subInstantiable_change_state_hook()
        del self.outputKey
        del self.storage
    def _outputKey(self):
        return '/'.join((
            super()._outputKey(),
            *(si.hashID for si in self._subInstantiators.values())
            ))
