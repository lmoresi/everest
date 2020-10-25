from functools import wraps
from collections.abc import Mapping, Sequence
from collections import OrderedDict
import warnings
import weakref

import numpy as np

from . import Proxy
from ._stateful import Stateful, Statelet, State
from ._applier import Applier
from ._configurator import Configurator
from ..utilities import w_hash, get_hash, is_numeric

from ..exceptions import *
class ConfigurableException(EverestException):
    pass
class ConfigurableMissingAsset(MissingAsset, ConfigurableException):
    pass
class ConfigurableAlreadyConfigured(ConfigurableException):
    pass
class CannotProcessConfigs(ConfigurableException):
    pass
class ConfigException(EverestException):
    pass
class ConfigMissingAsset(MissingAsset, ConfigException):
    pass
class ConfigCannotConvert(ConfigException):
    pass
class ConfigsException(EverestException):
    pass

class Config:
    def __init__(self, *args, content = None, **kwargs):
        self.content = content
        # super().__init__(*args, content = content, **kwargs)
    def _hashID(self):
        return get_hash(self.content, make = True)
    def apply(self, toVar):
        if not isinstance(toVar, Statelet):
            raise TypeError(type(toVar))
        self._apply(toVar)
    def _apply(self, toVar):
        toVar.mutate(self.content)
    @classmethod
    def convert(cls, arg, default = None, strict = False):
        if default is Ellipsis and not arg is Ellipsis:
            warnings.warn('Cannot reset Ellipsis default config: ignoring.')
            return Ellipsis
        else:
            if isinstance(arg, Proxy):
                arg = arg.realised
            if any([
                    isinstance(arg, (Config, Configurator)),
                    arg is Ellipsis,
                    ]):
                return arg
            elif not strict and any([
                    is_numeric(arg),
                    isinstance(type(arg), np.ndarray),
                    ]):
                return arg
            else:
                raise ConfigCannotConvert(repr(arg)[:100], type(arg))
    # @property
    # def var(self):
    #     return self._var()
    # def _var(self):
    #     raise ConfigMissingAsset

class Configs(Mapping, Sequence):

    def __init__(self, *args, **kwargs):
        pass
        # super().__init__(*args, **kwargs)
    @property
    def contents(self):
        return self._contentsDict

    def __getitem__(self, arg):
        if type(arg) is str:
            return self.contents[arg]
        else:
            return list(self.contents.values())[arg]
    def __len__(self):
        return len(self.contents)
    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def keys(self, *args, **kwargs):
        return list(self.contents.keys(*args, **kwargs))
    def values(self, *args, **kwargs):
        return list(self.contents.values(*args, **kwargs))
    def items(self, *args, **kwargs):
        return self.contents.items(*args, **kwargs)
    def apply(self, state):
        if not isinstance(state, State):
            raise TypeError
        if not [*state.keys()] == [*self.keys()]:
            raise KeyError(state.keys(), self.keys())
        self._apply(state)
    def _apply(self, state):
        if not isinstance(state, State):
            raise TypeError("Configs can only be applied to State.")
        for c, m in zip(self.values(), state):
            if not c is Ellipsis:
                if isinstance(c, (Configurator, Config)):
                    c.apply(m)
                else:
                    m.mutate(c)

    @property
    def id(self):
        return self.contentHash
    def _hashID(self):
        return w_hash(tuple(self.contents.items()))

class MutableConfigs(Configs):

    def __init__(self, defaults, *args, contents = None, **kwargs):
        if type(defaults) is type(self):
            defaults = defaults.contents.copy()
        elif not type(defaults) is OrderedDict:
            raise TypeError
        self.defaults = defaults
        self._contentsDict = self._align_inputs(*args, **kwargs)
        self._contentsDict.update(self._process_new(contents))
        for k, v in self._contentsDict.items():
            self._contentsDict[k] = Config.convert(v, self.defaults[k])
        super().__init__(
            defaults = self.defaults,
            contents = self._contentsDict,
            **kwargs,
            )
    def _process_new(self, new):
        if new is None:
            return dict()
        elif isinstance(new, Mapping):
            return {**new}
        elif isinstance(new, Sequence):
            return dict(zip(self.defaults.keys(), new))
        else:
            raise TypeError
    def _align_inputs(self, *args, **kwargs):
        ks = self.defaults.keys()
        new = {
            **self.defaults,
            **{k: v for k, v in zip(ks, args) if not v is None},
            **kwargs,
            }
        if not set(new.keys()) == set(ks):
            raise ValueError(
                "Keys did not match up:",
                (new.keys(), ks),
                )
        return OrderedDict([(k, new[k]) for k in ks])

    def __setitem__(self, arg1, arg2):
        arg2 = Config.convert(arg2, self.defaults[arg1])
        if type(arg1) is str:
            if not arg1 in self.keys():
                raise KeyError
            self.contents[arg1] = arg2
        elif issubclass(type(arg1), np.integer):
            self.contents[self.keys()[arg1]] = arg2
        elif type(arg1) is slice:
            rekeys = self.keys()[arg1]
            for k in rekeys:
                self.contents[k] = arg2
        else:
            raise ValueError

    def clear(self):
        self.contents.update(self.defaults)
    def update(self, inDict):
        for k, v in inDict.items():
            self[k] = v
    def update_generic(self, *args, **kwargs):
        self.contents.clear()
        self.contents.update(self._align_inputs(*args, **kwargs))
    def copy(self):
        return MutableConfigs(
            defaults = self.defaults,
            contents = self.contents.copy()
            )

class ImmutableConfigs(Configs):

    def __init__(self, *args, contents = OrderedDict(), **kwargs):
        self._contentsDict = contents.copy()
        super().__init__(*args, contents = contents, **kwargs)

class ConfigsHost(MutableConfigs):

    def __init__(self, host):
        self._host = weakref.ref(host)
        defaults = OrderedDict(
            (k, self.host.ghosts[k])
                for k in self.host._sortedGhostKeys[self.host._configsKey]
            )
        for k, v in defaults.items():
            if v is None:
                defaults[k] = float('NaN')
        self.configured = False
        self.stored = OrderedDict()
        super().__init__(defaults)

    @property
    def host(self):
        host = self._host()
        assert not host is None
        return host

    def set_configs(self, *args, new = None, **kwargs):
        prevHash = self.contentHash
        self._set_configs(*args, new = new, **kwargs)
        newHash = self.contentHash
        self.configured = newHash == prevHash and self.configured
        if newHash != prevHash:
            self.host._configurable_changed_state_hook()
    def _set_configs(self, *args, new = None, **kwargs):
        if new is None:
            new = self.merge_configs(*args, **kwargs)
        else:
            if len(args) or len(kwargs):
                raise ValueError
            new = self.process_configs(new)
        self.update(new)
    def merge_configs(self, *args, **kwargs):
        merged = self.copy()
        merged.update_generic(*args, **kwargs)
        return merged
    def process_configs(self, arg, strict = False):
        try:
            return self.merge_configs(Config.convert(arg, strict = strict))
        except ConfigCannotConvert:
            if isinstance(arg, Sequence):
                return self.merge_configs(*arg)
            elif isinstance(arg, Mapping):
                return self.merge_configs(**arg)
            else:
                raise CannotProcessConfigs
    def apply(self, silent = False):
        if self.configured:
            if silent:
                pass
            else:
                raise ConfigurableAlreadyConfigured
        else:
            super().apply(self.host.state)
            self.configured = True
            self.host._configurable_changed_state_hook()

    def store(self):
        k, v = self.id, ImmutableConfigs(contents = self.contents)
        self.stored[k] = v

    def __repr__(self):
        keyvalstr = ', '.join('=='.join((k, str(v)))
            for k, v in self.items()
            )
        return 'Configs:' + self.id + '{' + keyvalstr + '}'

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError

class Configurable(Stateful):

    _defaultConfigsKey = 'configs'

    def __init__(self, **kwargs):

        self._configsKey = self._defaultConfigsKey
        self._configs = None

        super().__init__(**kwargs)

    @property
    def configs(self):
        if self._configs is None:
            self._configs = ConfigsHost(self)
        return self._configs

    def _state_keys(self):
        for k in super()._state_keys(): yield k
        for k in self.configs.keys(): yield k

    def _configurable_changed_state_hook(self):
        pass

    def _outputSubKey(self):
        yield self.configs.contentHash
        for o in super()._outputSubKey(): yield o

    def _save(self):
        super()._save()
        self.writeouts.add_dict({self._configsKey: self.configs.contents})

    def _load(self, arg):
        if arg is None:
            self.configs.apply(silent = True)
        elif type(arg) is str:
            try:
                loadCon = self.configs.stored[arg]
            except KeyError:
                readpath = '/'.join([
                    self.outputMasterKey,
                    arg,
                    self._configsKey
                    ])
                loadCon = self.reader[readpath]
            self.configs.set_configs(**loadCon)
        else:
            super()._load(arg)

    def __setitem__(self, arg1, arg2):
        assert len(self.configs)
        if len(self.configs) == 1:
            self._configurable_set_single(arg1, arg2)
        else:
            self._configurable_set_multi(arg1, arg2)
    def _configurable_set_single(self, arg1, arg2):
        raise NotYetImplemented
    def _configurable_set_multi(self, arg1, arg2):
        if arg1 is Ellipsis:
            seqChoice = range(len(self.configs))
            mapChoice = self.configs.keys()
        elif type(arg1) is str:
            seqChoice = [list(self.configs.keys()).index(arg1),]
            mapChoice = [arg1,]
        elif type(arg1) is int:
            seqChoice = [arg1,]
            mapChoice = [list(self.configs.keys())[arg1],]
        elif type(arg1) is tuple:
            if len(set([type(o) for o in arg1])) > 1:
                raise ValueError
            if type(arg1[0]) is str:
                seqFn = lambda arg: list(self.configs.keys()).index(arg)
                seqChoice = [seqFn(arg) for arg in arg1]
                mapChoice = arg1
            elif type(arg1[0] is int):
                mapFn = lambda arg: list(self.configs.keys())[arg]
                seqChoice = arg1
                mapChoice = [mapFn(arg) for arg in arg1]
            else:
                raise TypeError
        if isinstance(arg2, Sequence):
            arg2 = [arg2[i] for i in seqChoice]
            self.configs.set_configs(*arg2)
        elif isinstance(arg2, Mapping):
            arg2 = OrderedDict((k, arg2[k]) for k in mapChoice)
            self.configs.set_configs(**arg2)
        else:
            arg2 = [arg2 for i in seqChoice]
            self.configs.set_configs(*arg2)
