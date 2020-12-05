from ptolemaic import Case

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

class TraversableCase(Case):
    ...
    # def __getitem__(case, args):
    #     if not type(args) is tuple:
    #         args = (args,)


class Traversable(Iterable, Configurable):

    @classmethod
    def _helperClasses(cls):
        d = super()._helperClasses()
        d['StateVar'][0].append(TraversableVar)
        d['Case'][0].insert(0, TraversableCase)
        return d

    def _subInstantiable_change_state_hook(self):
        super()._subInstantiable_change_state_hook()
        self.indices.nullify()

    def reset(self):
        self.configs.reset()
        self._subInstantiable_change_state_hook()
        super().reset()

    # def reach(self, configs, *args, **kwargs):
    #     self.configs[...] = configs
    #     if args:
    #         super().reach(*args, **kwargs)
    # def run(self, configs, *args, **kwargs):
    #     self.configs[...] = configs
    #     if args:
    #         super().run(*args, **kwargs)
