from collections import OrderedDict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
import warnings

import numpy as np

from funcy.variable import Array
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

class StateVar(Array):
    pass
    # def _set_value(self, val):
    #     super()._set_value(val)

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
        if not isinstance(state, DynamicState):
            raise TypeError("States can only be applied to other States.")
        if not [*state.keys()] == [*self.keys()]:
            raise KeyError(state.keys(), self.keys())
        state.mutate(self)

    def __str__(self):
        rows = []
        for k, v in self.items():
            row = k + ': '
            row += v.hashID if hasattr(v, 'hashID') else repr(v)
            rows.append(row)
        keyvalstr = ',\n    '.join(rows)
        return '{\n    ' + keyvalstr + ',\n    }'
    def __repr__(self):
        return type(self).__name__ + str(self)
    @property
    def hashID(self):
        return wordhash.w_hash(repr(self))
    @property
    def id(self):
        return self.hashID

class MutableState(State):
    def __setitem__(self, key, val):
        self.vars[key] = val

class DynamicState(State):
    def mutate(self, mutator):
        if isinstance(mutator, DynamicState):
            warnings.warn(
                "Mutating from mutable state: behaviour may be unpredictable."
                )
        for c, m in zip(mutator.values(), self.values()):
            if not c is Ellipsis:
                m.set(c)
    def __repr__(self):
        rows = (': '.join((k, v.valstr)) for k, v in self.items())
        keyvalstr = ',\n    '.join(rows)
        return type(self).__name__ + '{\n    ' + keyvalstr + ',\n    }'

class FrameState(DynamicState):

    def __init__(self, _stateVars, instanceID, stateVarClass):
        self.StateVar = stateVarClass
        self._vars = OrderedDict(
            (v.name, v) for v in _stateVars
            )
        for v in self._vars.values():
            assert isinstance(v, self.StateVar)
            v.sourceInstanceID = instanceID
        super().__init__()
    def mutate(self, mutator):
        if isinstance(mutator, FrameState):
            warnings.warn(
                "Attempting to set state from a mutable state - \
                behaviour is not guaranteed."
                )
        super().mutate(mutator)

    def load_process(self, outs):
        raise NotYetImplemented
        # outs = super(Stateful, self.frame)._load_process(outs)
        # for k, v in self.items():
        #     v.value = outs.pop(k)
        # return outs

class Stateful(Observable, Producer):

    @classmethod
    def _helperClasses(cls):
        d = super()._helperClasses()
        d['State'] = ([FrameState,], OrderedDict())
        d['StateVar'] = ([StateVar,], OrderedDict())
        return d

    def __init__(self,
            _stateVars = [],
            _outVars = [],
            **kwargs
            ):
        self.state = self.State(_stateVars, self.instanceID, self.StateVar)
        _outVars.extend(_stateVars)
        super().__init__(_outVars = _outVars, **kwargs)

    def _process_loaded(self, loaded):
        for key in self.state:
            self.state[key].set(loaded.pop(key))
        return super()._process_loaded(loaded)

    # def _save(self):
    #     return self.state.save()
    # def _load_process(self, outs):
    #     return self.state.load_process(outs)

    # def _load(self, arg, **kwargs):
    #     return self.state.load(arg, **kwargs)

    # def _out(self):
    #     outs = super()._out()
    #     if self._observationMode:
    #         add = {}
    #     else:
    #         add = self.state.out()
    #     outs.update(add)
    #     return outs
