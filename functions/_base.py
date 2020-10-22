import operator
import builtins
from types import FunctionType
from collections.abc import Mapping, Sequence
import weakref

import numpy as np

from ..pyklet import Pyklet
from ..utilities import w_hash, get_hash, is_numeric
from ..exceptions import *

class FunctionException(EverestException):
    pass
class FunctionMissingAsset(MissingAsset, FunctionException):
    pass
class NullValueDetected(FunctionException):
    pass
class EvaluationError(FunctionException):
    pass

class Function(Pyklet):

    def __new__(cls, *args, **kwargs):
        if cls is Function:
            if len(kwargs) == 0 and len(args) == 1:
                if isinstance(args[0], Function):
                    raise ValueError("Arg is already a Function.")
            cls = cls._getcls(*args, **kwargs)
        return super().__new__(cls)

    def __init__(self, *terms, name = None, **kwargs):
        self._name = name
        self.terms = [Function() if t is None else t for t in terms]
        if len(terms) == 1:
            self.arg = terms[0]
        else:
            self.arg = terms
        self.args = self.terms
        self.kwargs = {**kwargs}
        if not self._name is None:
            self.kwargs['name'] = self.name
        super().__init__(*self.args, **self.kwargs)

    @staticmethod
    def _value_resolve(val):
        while isinstance(val, Function):
            val = val.value
        return val
    def evaluate(self):
        if self.open:
            raise EvaluationError("Cannot evaluate open function.")
        else:
            return self._value_resolve(self._evaluate())
    def _evaluate(self):
        raise FunctionMissingAsset
    @property
    def value(self):
        return self.evaluate()
    @property
    def null(self):
        return self._isnull()
    def _isnull(self):
        return False
    @property
    def name(self):
        return str(self._name)

    def _count_slots(self):
        terms = self.terms
        argslots = 0
        kwargslots = []
        for term in terms:
            if isinstance(term, Function):
                if type(term) is Slot:
                    if term.argslots:
                        argslots += 1
                    elif not term.name in kwargslots:
                        kwargslots.append(term.name)
                else:
                    kwargslots.extend(
                        k for k in term.kwargslots if not k in kwargslots
                        )
                    argslots += term.argslots
        return argslots, kwargslots
    def _add_slot_attrs(self):
        if not '_slots' in dir(self):
            self._argslots, self._kwargslots = self._count_slots()
            self._slots = self._argslots + len(self._kwargslots)
        else:
            pass
    @property
    def slots(self):
        self._add_slot_attrs()
        return self._slots
    @property
    def argslots(self):
        self._add_slot_attrs()
        return self._argslots
    @property
    def kwargslots(self):
        self._add_slot_attrs()
        return self._kwargslots
    @property
    def open(self):
        return bool(self.slots)
    def close(self,
            *queryArgs,
            **queryKwargs
            ):
        badKeys = [k for k in queryKwargs if not k in self.kwargslots]
        if badKeys:
            raise FunctionException("Inappropriate kwargs:", badKeys)
        unmatchedKwargs = [k for k in self.kwargslots if not k in queryKwargs]
        if len(queryArgs) > self.argslots and len(unmatchedKwargs):
            excessArgs = queryArgs[-(len(queryArgs) - self.argslots):]
            extraKwargs = dict(zip(self.kwargslots, excessArgs))
            excessArgs = excessArgs[len(extraKwargs):]
            if len(excessArgs):
                raise FunctionException("Too many args:", excessArgs)
            queryKwargs.update(extraKwargs)
        queryArgs = iter(queryArgs[:self.argslots])
        terms = []
        changes = 0
        for t in self.terms:
            if type(t) is Slot:
                if t.argslots:
                    try:
                        t = next(queryArgs)
                        changes += 1
                    except StopIteration:
                        pass
                else:
                    if t.name in queryKwargs:
                        t = queryKwargs[t.name]
                        changes += 1
            elif isinstance(t, Function):
                if t.open:
                    queryArgs = list(queryArgs)
                    subArgs = queryArgs[:t.argslots]
                    leftovers = queryArgs[t.argslots:]
                    subKwargs = {
                        k: queryKwargs[k]
                            for k in queryKwargs if k in t.kwargslots
                        }
                    t = t.close(
                        *subArgs,
                        **subKwargs,
                        )
                    changes += 1
                    queryArgs = iter(leftovers)
            terms.append(t)
        if changes:
            outObj = type(self)(*terms, **self.kwargs)
        else:
            outObj = self
        return outObj

    def _operate(self, *args, op = None, **kwargs):
        return Operation(self, *args, op = op, **kwargs)

    def __eq__(self, *args):
        return self._operate(*args, op = 'eq', comparative = True)
    def __ne__(self, *args):
        return self._operate(*args, op = 'ne', comparative = True)
    def __ge__(self, *args):
        return self._operate(*args, op = 'ge', comparative = True)
    def __le__(self, *args):
        return self._operate(*args, op = 'le', comparative = True)
    def __gt__(self, *args):
        return self._operate(*args, op = 'gt', comparative = True)
    def __lt__(self, *args):
        return self._operate(*args, op = 'lt', comparative = True)
    def __and__(self, *args):
        return self._operate(*args, op = 'all', comparative = True)
    def __or__(self, *args):
        return self._operate(*args, op = 'any', comparative = True)
    def __add__(self, *args):
        return self._operate(*args, op = 'add')
    def __floordiv__(self, *args):
        return self._operate(*args, op = 'floordiv')
    def __truediv__(self, *args):
        return self._operate(*args, op = 'truediv')
    def __mod__(self, *args):
        return self._operate(*args, op = 'mod')
    def __mul__(self, *args):
        return self._operate(*args, op = 'mul')
    def __pow__(self, *args):
        return self._operate(*args, op = 'pow')
    def __sub__(self, *args):
        return self._operate(*args, op = 'sub')
    def __truediv__(self, *args):
        return self._operate(*args, op = 'truediv')
    def __neg__(self, *args):
        return self._operate(*args, op = 'neg')

    def __bool__(self):
        try:
            return bool(self.value)
        except NullValueDetected:
            return False
    @staticmethod
    def bool(arg):
        return Operation(*args, op = bool)
    @staticmethod
    def all(*args):
        return Operation(*args, op = all)
    @staticmethod
    def any(*args):
        return Operation(*args, op = any)
    @staticmethod
    def not_fn(*args):
        return Operation(*args, op = bool, invert = True)
    def __invert__(self):
        return self.not_fn(self)

    def pipeout(self, arg):
        if not isinstance(arg, (Array, Value)):
            raise FunctionException("Can only pipe to Arrays or Values.")
        return arg.pipein(self)

    def __rshift__(self, arg):
        return self.pipeout(arg)
    def __lshift__(self, arg):
        return arg.pipeout(self)

    def __repr__(self):
        head = super().__repr__()
        tail = str(self)
        return '=='.join([head, tail])
    def __str__(self):
        if self.open:
            return 'open:' + str((self.argslots, self.kwargslots))
        else:
            try:
                return str(self.value)
            except (NullValueDetected, EvaluationError):
                return 'Null'
    def __call__(self, *args, **kwargs):
        if len(args) or len(kwargs):
            self = self.close(*args, **kwargs)
        return self.evaluate()

    @staticmethod
    def _getop(op):
        if op is None:
            return lambda *args: args
        elif type(op) is str:
            try:
                return getattr(builtins, op)
            except AttributeError:
                return getattr(operator, op)
        else:
            return op

    @classmethod
    def _getcls(cls, *args, op = None, **kwargs):
        if op is None:
            if not len(args):
                return Slot
            elif len(args) > 1:
                return Seq
            else:
                arg = args[0]
                if is_numeric(arg):
                    return Value
                elif type(arg) is str:
                    return Text
                else:
                    try:
                        _ = len(arg)
                        return Array
                    except TypeError:
                        return Thing
        else:
            return Operation

    @property
    def get(self):
        return Getter(self)
    def __getitem__(self, key):
        return self.value[key]

    def op(self, arg, **kwargs):
        return Operation(self, op = arg, **kwargs)

    def exc(self, exc = Exception, altval = None):
        return Trier(self, exc = exc, altval = altval)

class Getter:
    def __init__(self, host):
        self.host = host
    def __call__(self, *props):
        return GetAttr(self.host, *props)
    def __getitem__(self, key):
        return GetItem(self.host, key)

from ._operation import Operation
from ._get import GetAttr, GetItem
from ._trier import Trier
from ._seq import Seq
from ._value import Value
from ._array import Array
from ._text import Text
from ._thing import Thing
from ._slot import Slot
