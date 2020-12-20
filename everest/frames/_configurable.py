from collections.abc import Mapping
from collections import OrderedDict

import numpy as np

from everest.ptolemaic.frames.stateful import Stateful
from everest.ptolemaic.frames.bythic import Bythic
from everest.ptolemaic.display import Reportable
from everest.funcy.map import SettableMap

from ._configurator import Configurator
from ..utilities import ordered_unpack
from ..exceptions import *

class Configurable(Stateful, Bythic):

    @classmethod
    def _configs_construct(cls):
        class Configs(Reportable, SettableMap):
            def __init__(self, frame):
                self.state = frame.state
                keys, values = zip(*frame.ghosts.configs.items())
                values = tuple(self._process_value(v) for v in values)
                super().__init__(keys, values)
            def _process_value(self, v):
                if isinstance(v, self.state.StateVar):
                    v = Ellipsis
                elif type(v) is tuple:
                    _, v = v
                return v
            def __setitem__(self, *args, **kwargs):
                super().__setitem__(*args, **kwargs)
                self.state.nullify()
            def apply(self):
                self.state[...] = self
        cls.Configs = Configs
        return

    @classmethod
    def _class_construct(cls):
        super()._class_construct()
        cls._configs_construct()
        return

    def __init__(self,
            _stateVars = None,
            **kwargs
            ):
        _stateVars = dict() if _stateVars is None else _stateVars
        super().__init__(
            _stateVars = {**_stateVars, **self.ghosts.configs},
            **kwargs
            )
        self.configs = self.Configs(self)

    def reset(self):
        self.configs.reset()

    def _setitem(self, keyvals):
        super()._setitem(keyvals)
        k, v = keyvals.popleft()
        if k is Ellipsis: pass
        elif type(k) is tuple: pass
        elif k == 'configs': pass
        else:
            keyvals.appendleft(k, v)
            return
        self.configs[k] = v
        self._producer_purge()

    def _outputKey(self):
        return '/'.join((
            super()._outputKey(),
            self.configs.hashID,
            ))


#
# class Configs(State):
#     def __init__(self,
#             contents
#             ):
#         self._vars = OrderedDict(
#             (k, self._process_config(v))
#                 for k, v in contents.items()
#             )
#         super().__init__()
#     @staticmethod
#     def _process_config(v):
#         if isinstance(v, Configurator):
#             return v
#         else:
#             if v is None:
#                 v = float('nan')
#             return v
#
# class MutableConfigs(MutableState, Configs):
#     def __init__(self, defaults):
#         super().__init__(defaults)
#         self.defaults = self.vars.copy()
#     def __setitem__(self, arg1, arg2):
#         for k, v in ordered_unpack(self.keys(), arg1, arg2).items():
#             if not k in self.keys():
#                 raise KeyError("Key not in configs: ", k)
#             v = self[k] if v is None else self._process_config(v)
#             super().__setitem__(k, v)
#     def reset(self):
#         self.update(self.defaults)
#     def update(self, arg):
#         self[...] = arg
#     def copy(self):
#         out = MutableConfigs(self.defaults)
#         out.update(self.vars)
#         return out

    # def store(self):
    #     k, v = self.id, Configs(contents = self.vars)
    #     self.stored[k] = v
    # def load(self, id):
    #     self.update(self.stored[id])
    #
    # def __setitem__(self, key, val):
    #     super().__setitem__(key, val)
    #     self.frame._configurable_changed_state_hook()


    # @classmethod
    # def _frameClasses(cls):
    #     d = super()._frameClasses()
    #     d['Configs'] = ([FrameConfigs,], OrderedDict())
    #     return d

    # def __setitem__(self, key, val):
    #     if type(key) is tuple:
    #         raise ValueError
    #     if type(key) is slice:
    #         raise NotYetImplemented
    #     self.configs[key] = val
    #     self._configurable_changed_state_hook()

    # def _save(self):
    #     super()._save()
    #     self.writeouts.add_dict({'configs': self.configs.vars})

    # def _load(self, arg, **kwargs):
    #     if arg is None:
    #         self.configs.apply()
    #     elif type(arg) is str:
    #         try:
    #             self.configs.load(arg)
    #         except KeyError:
    #             # may be problematic
    #             readpath = '/'.join([
    #                 self.outputMasterKey,
    #                 arg,
    #                 'configs',
    #                 ])
    #             self.configs[...] = self.reader[readpath]
    #     else:
    #         super()._load(arg, **kwargs)
