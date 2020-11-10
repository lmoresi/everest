import numbers
import numpy as np

from ._indexable import Indexable, IndexVar

class Chronable(Indexable):

    def __init__(self,
            _indices = [],
            **kwargs
            ):
        var = IndexVar(
            np.float32,
            compType = numbers.Real,
            name = 'chron',
            )
        super().__init__(
            _indices = [var, *_indices],
            **kwargs
            )
