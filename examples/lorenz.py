from everest.frames._traversable import Traversable
from everest.frames._stateful import StateVar

class Lorenz(Traversable):

    def __init__(self,
            # _configs
                x = 0.,
                y = 0.,
                z = 0.,
            # params
                s = 10,
                r = 28,
                b = 2.667,
            **kwargs
            ):

        super().__init__(**kwargs)

        self._stateVars = [
            StateVar(x, name = 'x'),
            StateVar(y, name = 'y'),
            StateVar(z, name = 'z'),
            ]

    def _state_vars(self):
        for o in super()._state_vars(): yield o
        for v in self._stateVars: yield v

    def _iterate(self, **kwargs):
        x, y, z = self.state.values()
        s, r, b = self.inputs.params.values()
        x_dot = (y - x) * s
        y_dot = x * r - y - x * z
        z_dot = x * y - z * b
        x.value, y.value, z.value = x_dot, y_dot, z_dot
        super()._iterate(**kwargs)
