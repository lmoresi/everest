from ._producer import Producer
from ._subinstantiable import SubInstantiable

class SubOutputable(Producer, SubInstantiable):
    def __init__(self,
            **kwargs,
            ):
        super().__init__(**kwargs)
    def _subInstantiable_change_state_hook(self):
        super()._subInstantiable_change_state_hook()
        try: del self.outputKey
        except AttributeError: pass
        try: del self.storage
        except AttributeError: pass
    def _outputKey(self):
        return '/'.join((
            super()._outputKey(),
            *(si.hashID for si in self._subInstantiators.values())
            ))
