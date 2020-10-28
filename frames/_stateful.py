from collections import OrderedDict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import numpy as np

import funcy

from ._producer import Producer, Outs
from ._observable import Observable
from ..hosted import Hosted
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

    def __init__(self):
        for k, v in self.items():
            setattr(self, k, v)

    @property
    def vars(self):
        try:
            return self._vars
        except AttributeError:
            raise MissingAsset(
                "Classes inheriting from State must provide _vars attribute."
                )

    def __getitem__(self, key):
        if type(key) is str:
            return self.vars[key]
        else:
            return list(self.values())[key]
    def __len__(self):
        return len(self.vars)
    def __iter__(self):
        return iter(self.vars)

    def apply(self, state):
        if not isinstance(state, State):
            raise TypeError("States can only be applied to other States.")
        if not [*state.keys()] == [*self.keys()]:
            raise KeyError(state.keys(), self.keys())
        self._apply(state)
    def _apply(self, state):
        for c, m in zip(self.values(), state.values()):
            if not c is Ellipsis:
                try:
                    c.apply(m)
                except AttributeError:
                    m.value = c

    @property
    def id(self):
        return self.hashID
    @property
    def hashID(self):
        return w_hash(repr(self))
    def __repr__(self):
        keyvalstr = ', '.join(' == '.join((k, str(v)))
            for k, v in self.items()
            )
        return type(self).__name__ + '{' + keyvalstr + '}'

class DynamicState(State, Hosted):

    def __init__(self, host):
        Hosted.__init__(self, host)
        State.__init__(self)
    @property
    def _vars(self):
        return OrderedDict(zip(
            tuple([*self.host._state_keys()][1:]),
            tuple([*self.host._state_vars()][1:]),
            ))

    def out(self):
        return OrderedDict(zip(
            self.keys(),
            (v.data for v in self.values())
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

class Stateful(Observable, Producer):

    def __init__(self,
            **kwargs
            ):

        self._state = None

        super().__init__(**kwargs)

    @property
    def state(self):
        if self._state is None:
            self._state = DynamicState(self)
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
