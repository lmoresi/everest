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
                x = 0.,
                y = 1.,
                z = 1.05,
            **kwargs
            ):

        super().__init__(**kwargs)

        x, y, z = self.state.values()
        self._chronVar = self.indices['chron']
        def lorenz():
            xi, yi, zi = x.data, y.data, z.data
            return (
                s*(yi - xi),
                r*xi - yi - xi*zi,
                xi*yi - b*zi,
                )
        def _integrate():
            for v, dot in zip(
                    (x, y, z),
                    lorenz()
                    ):
                v.data += dot * dt
            self._chronVar += dt
        self._integrate = _integrate

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
