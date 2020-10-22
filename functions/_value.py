import numpy as np

from ..utilities import is_numeric

from ._base import Function
from ._base import \
    FunctionException, FunctionMissingAsset, NullValueDetected, EvaluationError

class Value(Function):

    def __init__(self,
            arg,
            initial = None,
            name = None
            ):

        super().__init__(
            arg,
            initial = initial,
            name = name
            )

        self._value = None

        if isinstance(arg, Function):
            if not is_numeric(initial):
                raise ValueError
            null = False
            pipe = arg
            value = initial
        elif is_numeric(arg):
            if initial == 'null':
                null = True
            elif initial is None:
                null = False
            else:
                raise ValueError
            pipe = None
            value = arg
        else:
            raise TypeError("Value must be numeric or Function type.")
        if np.issubdtype(type(value), np.integer):
            dtype = np.int32
        else:
            dtype = np.float64
        value = dtype(value)

        self.dtype = dtype
        self.pipe = pipe
        if null:
            self.value = None
        else:
            self.value = value

    def _isnull(self):
        return self._value is None

    def __setattr__(self, key, value):
        if key == 'value':
            if value is None:
                self._value = None
                return None
            else:
                try:
                    if np.issubdtype(type(value), np.integer):
                        plain = int(value)
                    else:
                        plain = float(value)
                    value = self.dtype(value)
                    self._value = value
                except TypeError:
                    raise TypeError((value, type(value)))
                return None
        else:
            super().__setattr__(key, value)

    def _evaluate(self):
        if not self.pipe is None:
            self.value = self._value_resolve(self.pipe)
        if self.null: raise NullValueDetected(self._value)
        return self._value

    def _reassign(self, arg, op = None):
        if self.pipe is None:
            self.value = self._operate(arg, op = op).value
            return self
        else:
            return Value(self.pipe + arg, **self.kwargs)
    def __iadd__(self, arg): return self._reassign(arg, op = 'add')
    def __ifloordiv__(self, arg): return self._reassign(arg, op = 'floordiv')
    def __imod__(self, arg): return self._reassign(arg, op = 'mod')
    def __imul__(self, arg): return self._reassign(arg, op = 'mul')
    def __ipow__(self, arg): return self._reassign(arg, op = 'pow')
    def __isub__(self, arg): return self._reassign(arg, op = 'sub')
    def __itruediv__(self, arg): return self._reassign(arg, op = 'truediv')

    def pipein(self, arg):
        if not isinstance(arg, Function):
            raise FunctionException
        return Value(
            arg,
            initial = self._value,
            name = self.name
            )

    def _hashID(self):
        return self.name
