import numpy as np

from everest.frames._traversable import Traversable
from everest.frames._chronable import Chronable

class Lorenz(Traversable, Chronable):

    def __init__(self,
            # params
                s = 10,
                r = 28,
                b = 2.667,
                dt = 0.01,
            # _configs
                coords = [0., 1., 1.05],
                # x = 0.,
                # y = 1.,
                # z = 1.05,
            **kwargs
            ):

        super().__init__(**kwargs)

        cs = self.state['coords'].data
        chron = self.indices['chron']
        def integrate():
            cs[...] = (
                cs[0] + dt * (s * (cs[1] - cs[0])),
                cs[1] + dt * (r * cs[0] - cs[1] - cs[0] * cs[2]),
                cs[2] + dt * (cs[0] * cs[1] - b * cs[2]),
                )
            chron.data = chron.data + dt
        self._integrate = integrate

    def _iterate(self, **kwargs):
        self._integrate()
        super()._iterate(**kwargs)

    # def _iterate(self, **kwargs):
    #     coords = self.state.values()
    #     newcoords = lorenz(coords, *self.inputs.params.values())
    #     for c, nc in zip(coords, newcoords):
    #         c.value = nc

        # x, y, z = self.state.values()
        # self._iterFns = [
        #     ((y - x) * s) * dt,
        #     (x * r - y - x * z) * dt,
        #     (x * y - z * b) * dt,
        #     ]
