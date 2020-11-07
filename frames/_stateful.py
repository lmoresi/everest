from collections import OrderedDict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import warnings

import numpy as np

import funcy
import wordhash

from ._producer import Producer
from ._observable import Observable
from ._applier import Applier
from ..hosted import Hosted

from ..exceptions import *
class StatefulException(EverestException):
    pass
class StatefulMissingAsset(MissingAsset, StatefulException):
    pass
class RedundantApplyState(StatefulException):
    pass

class StateVar(funcy.FixedVariable):
    def _set_value(self, val):
        super()._set_value(val)

class State(Sequence, Mapping):

    def __init__(self):
        pass

    @property
    def vars(self):
        try:
            return self._vars
        except AttributeError:
            raise MissingAsset(
                self,
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
        if not isinstance(state, MutableState):
            raise TypeError("States can only be applied to other States.")
        if not [*state.keys()] == [*self.keys()]:
            raise KeyError(state.keys(), self.keys())
        state.mutate(self)

    def __repr__(self):
        rows = []
        for k, v in self.items():
            row = k + ': '
            row += v.hashID if hasattr(v, 'hashID') else repr(v)
            rows.append(row)
        keyvalstr = ',\n    '.join(rows)
        return type(self).__name__ + '{\n    ' + keyvalstr + ',\n    }'
    @property
    def hashID(self):
        return wordhash.w_hash(repr(self))
    @property
    def id(self):
        return self.hashID

class MutableState(State):
    def mutate(self, mutator):
        if isinstance(mutator, MutableState):
            warnings.warn(
                "Mutating from mutable state: behaviour may be unpredictable."
                )
        for c, m in zip(mutator.values(), self.values()):
            if not c is Ellipsis:
                m.value = c
    def __repr__(self):
        rows = (': '.join((k, v.valstr)) for k, v in self.items())
        keyvalstr = ',\n    '.join(rows)
        return type(self).__name__ + '{\n    ' + keyvalstr + ',\n    }'

class FrameState(MutableState, Hosted):

    def __init__(self, host):
        Hosted.__init__(self, host)
        State.__init__(self)
    @property
    def _vars(self):
        return OrderedDict(zip(
            tuple([*self.frame._state_keys()][1:]),
            tuple([*self.frame._state_vars()][1:]),
            ))
    def mutate(self, mutator):
        if isinstance(mutator, FrameState):
            warnings.warn(
                "Attempting to set state from a mutable state - \
                behaviour is not guaranteed."
                )
        super().mutate(mutator)

    def out(self):
        return OrderedDict(zip(
            self.keys(),
            (v.data.copy() for v in self.values())
            ))
    def save(self):
        return super(Stateful, self.frame)._save()
    def load_process(self, outs):
        outs = super(Stateful, self.frame)._load_process(outs)
        for k, v in self.items():
            v.value = outs.pop(k)
        return outs
    # def load(self, arg, **kwargs):
    #     return super(Stateful, self.frame)._load(arg, **kwargs)

    @property
    def data(self):
        return self.out()

class Stateful(Observable, Producer):

    def __init__(self,
            **kwargs
            ):
        self._state = None
        super().__init__(**kwargs)

    @property
    def state(self):
        if self._state is None:
            self._state = FrameState(self)
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
    # def _load(self, arg, **kwargs):
    #     return self.state.load(arg, **kwargs)
