from ._iterable import Iterable
from ._stateful import State
from ._configurable import Configurable

from ..exceptions import *
class TraversableException(EverestException):
    pass

class TraversableVar:
    def _set_value(self, mutator):
        try:
            if v.sourceInstanceID == self.sourceInstanceID:
                raise ValueError("Circular state var reference.")
        except AttributeError:
            pass
        super()._set_value(mutator)

class Traversable(Iterable, Configurable):

    @classmethod
    def _helperClasses(cls):
        d = super()._helperClasses()
        d['StateVar'][0].append(TraversableVar)
        return d

    def _subInstantiable_change_state_hook(self):
        super()._subInstantiable_change_state_hook()
        self.indices.isnullify()

    def reset(self):
        self.configs.reset()
        self._subInstantiable_change_state_hook()
        super().reset()

    def reach(self, configs, *args, **kwargs):
        self[...] = configs
        if len(args):
            super().reach(*args, **kwargs)
    def run(self, configs, *args, **kwargs):
        self[...] = configs
        if len(args):
            super().run(*args, **kwargs)
