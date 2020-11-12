import numbers
import numpy as np

from ._indexable import Indexable

class Chronable(Indexable):

    def __init__(self,
            _indices = [],
            **kwargs
            ):
        var = self.IndexVar(
            np.float32,
            compType = numbers.Real,
            name = 'chron',
            )
        _indices.append(var)
        super().__init__(
            _indices = _indices,
            **kwargs
            )
