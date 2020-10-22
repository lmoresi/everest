from ._base import Function
from ._base import \
    FunctionException, FunctionMissingAsset, NullValueDetected, EvaluationError

class Operation(Function):

    def __init__(self,
            *terms,
            op = None,
            asList = False,
            invert = False,
            comparative = False
            ):
        if len(terms) == 1:
            if isinstance(terms[0], Seq):
                terms = tuple([*terms[0]])
        if type(op) is tuple:
            sops, op = op[:-1], op[-1]
            for sop in sops:
                terms = Operation(*terms, op = sop)
                if not type(terms) is tuple:
                    terms = terms,
        self.operation = self._getop(op)
        self.asList, self.invert = asList, invert
        self.comparative = comparative
        super().__init__(
            *terms,
            op = op,
            asList = asList,
            invert = invert,
            comparative = comparative
            )

    def _evaluate(self):
        try:
            ts = [self._value_resolve(t) for t in self.terms]
            if self.asList:
                out = self.operation(ts)
            else:
                out = self.operation(*ts)
            if self.invert:
                out = not out
            return out
        except NullValueDetected:
            if self.comparative:
                return False
            else:
                raise NullValueDetected

from ._seq import Seq
