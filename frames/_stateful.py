from collections import OrderedDict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import weakref

import numpy as np

import funcy

from ._producer import Producer, Outs
from ._observable import Observable
from ..utilities import make_hash, w_hash, get_hash

from ..exceptions import *
class StatefulException(EverestException):
    pass
class StatefulMissingAsset(MissingAsset, StatefulException):
    pass

class StateVar(funcy.FixedVariable):
    def _set_value(self, val):
        super()._set_value(val)

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
            v.value = outs.pop(k)
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
