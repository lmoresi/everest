from ._base import Function
from ._base import \
    FunctionException, FunctionMissingAsset, NullValueDetected, EvaluationError

class Trier(Function):
    def __init__(self, tryFunc, exc = Exception, altVal = None):
        if not isinstance(tryFunc, Function):
            raise TypeError
        if not type(exc) is tuple:
            excTuple = (exc,)
        for e in excTuple:
            if not (isinstance(e, Exception) or issubclass(e, Exception)):
                raise TypeError
        self.tryFunc, self.exc, self.altVal = tryFunc, exc, altVal
        super().__init__(tryFunc, exc = exc, altVal = altVal)
    def _evaluate(self):
        try:
            return self.tryFunc.value
        except self.exc:
            return self.altVal
