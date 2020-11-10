from collections.abc import Mapping
from collections import OrderedDict

import numpy as np

from ._stateful import Stateful, State, DynamicState, MutableState, StateVar
from ._configurator import Configurator
from ..hosted import Hosted
from ..utilities import ordered_unpack
from ..exceptions import *

class Configs(State):
    def __init__(self,
            contents
            ):
        self._vars = OrderedDict(
            (k, self._process_config(v))
                for k, v in contents.items()
            )
        super().__init__()
    @staticmethod
    def _process_config(v):
        if isinstance(v, Configurator):
            return v
        else:
            if v is None:
                v = float('nan')
            return v

class MutableConfigs(MutableState, Configs):
    def __init__(self, defaults):
        super().__init__(defaults)
        self.defaults = self.vars.copy()
    def __setitem__(self, arg1, arg2):
        for k, v in ordered_unpack(self.keys(), arg1, arg2).items():
            if not k in self.keys():
                raise KeyError("Key not in configs: ", k)
            v = self.defaults[k] if v is None else self._process_config(v)
            super().__setitem__(k, v)
    def clear(self):
        self.update(self.defaults)
    def update(self, arg):
        self[...] = arg
    def copy(self):
        out = MutableConfigs(self.defaults)
        out.update(self.vars)
        return out

class FrameConfigs(MutableConfigs, Hosted):

    def __init__(self, host):
        Hosted.__init__(self, host)
        defaults = OrderedDict(**self.frame.ghosts.configs)
        MutableConfigs.__init__(self, defaults)
        self.stored = OrderedDict()
        self.stateVars = [self._process_default(k, v) for k, v in self.items()]
    @staticmethod
    def _process_default(k, v):
        if isinstance(v, StateVar):
            return v
        elif type(v) is tuple:
            return v[0](v[1], name = k)
        else:
            return StateVar(v, name = k)

    def store(self):
        k, v = self.id, Configs(contents = self.vars)
        self.stored[k] = v
    def load(self, id):
        self.update(self.stored[id])

    def apply(self, arg = None):
        if arg is None:
            arg = self.frame.state
        super().apply(arg)

    def __setitem__(self, key, val):
        super().__setitem__(key, val)
        self.frame._configurable_changed_state_hook()

class Configurable(Stateful):

    _defaultConfigsKey = 'configs'

    def __init__(self,
            **kwargs
            ):
        self._configsKey = self._defaultConfigsKey
        self.configs = FrameConfigs(self)
        super().__init__(**kwargs)

    def _vector(self):
        for pair in super()._vector(): yield pair
        yield ('configs', self.configs)

    def _state_keys(self):
        for k in super()._state_keys(): yield k
        for k in self.configs.keys(): yield k

    def _state_vars(self):
        for v in super()._state_vars(): yield v
        for v in self.configs.stateVars: yield v

    def _configurable_changed_state_hook(self):
        self.outputKey = 'outputs/' + self.configs.hashID

    # def _outputSubKey(self):
    #     yield self.configs.hashID
    #     for o in super()._outputSubKey(): yield o

    def _save(self):
        super()._save()
        self.writeouts.add_dict({self._configsKey: self.configs.vars})

    def _load(self, arg, **kwargs):
        if arg is None:
            self.configs.apply()
        elif type(arg) is str:
            try:
                self.configs.load(arg)
            except KeyError:
                # may be problematic
                readpath = '/'.join([
                    self.outputMasterKey,
                    arg,
                    self._configsKey
                    ])
                self.configs[...] = self.reader[readpath]
        else:
            super()._load(arg, **kwargs)

    def __setitem__(self, key, val):
        if type(key) is tuple:
            raise ValueError
        if type(key) is slice:
            raise NotYetImplemented
        self.configs[key] = val
