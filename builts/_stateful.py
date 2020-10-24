from collections import OrderedDict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import weakref

import numpy as np

from ._producer import Producer, Outs
from ._observable import Observable
from .. import Pyklet
from ..utilities import make_hash, w_hash, get_hash

from . import BuiltException, MissingMethod, MissingAttribute, MissingKwarg
from ..exceptions import EverestException
class StatefulException(BuiltException):
    pass
class StatefulMissingMethod(MissingMethod, StatefulException):
    pass
class StatefulMissingAttribute(MissingAttribute, StatefulException):
    pass
class StatefulMissingKwarg(MissingKwarg, StatefulException):
    pass
class StateletException(EverestException):
    pass
class StateletMissingMethod(EverestException):
    pass

class Statelet:
    def __init__(self, var, name):
        self._var, self._name = var, name
        super().__init__()
    def _hashID(self):
        return '_'.join([self.name, get_hash(self.var)])
    @property
    def var(self):
        return self._var
    @property
    def name(self):
        return self._name
    @property
    def varHash(self):
        return make_hash(self.out())
    def out(self):
        return self._out()
    def _out(self):
        if not isinstance(self.var, np.ndarray):
            raise StateletMissingMethod(
                "If var is not an array, provide a custom _out method."
                )
        return self.var.copy()
    @property
    def data(self):
        return self._data()
    def _data(self):
        if not isinstance(self.var, np.ndarray):
            raise StateletMissingMethod(
                "If var is not an array, provide a custom _data method."
                )
        return self.var
    def mutate(self, vals, indices = Ellipsis):
        return self._mutate(vals, indices)
    def _mutate(self, vals, indices = Ellipsis):
        self.data[indices] = vals
    def imitate(self, fromVar):
        if not type(fromVar) is type(self):
            raise TypeError
        self._imitate(fromVar)
    def _imitate(self, fromVar):
        self.mutate(fromVar.data)

    def __getitem__(self, arg):
        return self.out()[arg]
    def __setitem__(self, key, val):
        self.mutate(val, indices = key)

class State(Sequence, Mapping):

    def __init__(self, host):
        self._host = weakref.ref(host)
        super().__init__()

    @property
    def host(self):
        host = self._host()
        assert not host is None
        return host

    @property
    def vars(self):
        return tuple([*self.host._state_vars()][1:])
    def keys(self):
        return tuple([*self.host._state_keys()][1:])
    @property
    def asdict(self):
        return OrderedDict(zip(self.keys(), self.vars))
    def items(self):
        return self.asdict.items()
    def values(self):
        return self.asdict.values()

    def out(self):
        return OrderedDict(zip(
            self.keys(),
            (v.data.copy() for v in self.vars)
            ))

    def save(self):
        return super(Stateful, self.host)._save()

    def load_process(self, outs):
        outs = super(Stateful, self.host)._load_process(outs)
        for k, v in self.items():
            v.mutate(outs.pop(k))
        return outs

    def load(self, arg):
        return super(Stateful, self.host)._load(arg)

    def __getitem__(self, key):
        try:
            return self.asdict[key]
        except KeyError:
            return self.vars[key]
    def __len__(self):
        return len(self.vars)
    def __iter__(self):
        for v in self.vars:
            yield v

    def __getattr__(self, key):
        try:
            return self.asdict[key]
        except KeyError:
            raise AttributeError

    def __repr__(self):
        keyvalstr = ', '.join('=='.join((k, str(v)))
            for k, v in self.items()
            )
        return 'State{' + keyvalstr + '}'

class Stateful(Observable, Producer):

    def __init__(self,
            **kwargs
            ):

        self._state = None

        super().__init__(**kwargs)

    @property
    def state(self):
        if self._state is None:
            self._state = State(self)
        return self._state

    def _state_vars(self):
        yield None
    def _state_keys(self):
        yield None

    def _out(self):
        outs = super()._out()
        if self._observationMode:
            add = {}
        else:
            add = self.state.out()
        outs.update(add)
        return outs
    def _save(self):
        return self.state.save()
    def _load_process(self, outs):
        return self.state.load_process(outs)
    def _load(self, arg):
        return self.state.load(arg)
