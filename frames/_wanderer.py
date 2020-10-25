import numpy as np
from collections import OrderedDict, namedtuple
from contextlib import contextmanager
from functools import wraps
import warnings
import weakref

from funcy import Function

from ..utilities import w_hash, get_hash
from ._producer import NullValueDetected, OutsNull
from ._voyager import Voyager, _voyager_initialise_if_necessary
from ._stampable import Stampable, Stamper
from ._stateful import State, Statelet
from ._configurable import \
    Configurable, MutableConfigs, ImmutableConfigs, Configs, Config, \
    CannotProcessConfigs
from ._configurator import Configurator
from ._indexer import IndexerLoadRedundant, IndexerLoadFail
from ..exceptions import *

class WandererException(EverestException):
    pass

class WildConfigsException(EverestException):
    pass
class RedundantWildConfigs(WildConfigsException):
    pass

def _wild_context_wrap(func):
    @wraps(func)
    def wrapper(wild, *args, **kwargs):
        if not wild._computed:
            wild._compute()
        return func(wild, *args, **kwargs)
    return wrapper

class WildConfigs(Stamper, ImmutableConfigs):
    _premade = weakref.WeakValueDictionary()
    @classmethod
    def get_wild(cls, wanderer, slicer):
        obj = cls(wanderer, slicer)
        try:
            obj = cls._premade[obj.contentHash]
        except KeyError:
            cls._premade[obj.contentHash] = obj
        return obj
    def __init__(self, wanderer, slicer):
        self.start, self.stop = get_start_stop(wanderer, slicer)
        self.indexlike = hasattr(self.stop, 'index')
        self._wildArgs = (wanderer, (self.start, self.stop))
        wildconfigs = OrderedDict([
            (k, WildConfig(self, k))
                for k in wanderer.configs.keys()
            ])
        wildconfigs = wanderer.configs.process_configs(wildconfigs)
        self._computed = False
        self.wanderer = wanderer.copy()
        super().__init__(self,
            contents = wildconfigs,
            )
    def _pickle(self):
        return self._wildArgs, OrderedDict()
    def _compute(self):
        assert not self._computed
        self.wanderer.go(self.start, self.stop)
        self._data = self.wanderer.out()
        self._data.name = self.wanderer.outputSubKey
        iks = self.wanderer.indices.keys()
        self._indices = namedtuple('IndexerHost', iks)(
            *[i.value for i in self.wanderer.indices]
            )
        self._computed = True
    @property
    @_wild_context_wrap
    def data(self):
        return self._data
    @property
    @_wild_context_wrap
    def indices(self):
        return self._indices
    @property
    @_wild_context_wrap
    def state(self):
        return self.wanderer.state

class WildConfig(Config):
    def __init__(self, wild, channel):
        self.wild, self.channel = wild, channel
        self._wildconfigHashID = self._make_hashID(
            self.channel,
            *self.wild._wildArgs
            )
        super().__init__(content = (self.channel, self.wild._wildArgs))
    @staticmethod
    def _make_hashID(channel, wanderer, sliceTup):
        if wanderer.configs[channel] is Ellipsis:
            return w_hash(str(Ellipsis))
        else:
            return w_hash((
                channel,
                wanderer.hashID,
                *[o.contentHash if hasattr(o, 'contentHash') else get_hash(o)
                    for o in sliceTup]
                ))
    def _hashID(self):
        return self._wildconfigHashID
    def _pickle(self):
        return (self.wild, self.channel), OrderedDict()
    @property
    def data(self):
        return self.wild.data[self.channel]
    @property
    def statelet(self):
        return self.wild.state[self.channel]
    def _apply(self, toVar):
        toVar.imitate(self.statelet)

def _de_comparator(obj):
    if isinstance(obj, Function) and hasattr(obj, 'index'):
        return obj.index
    else:
        return obj

def get_start_stop(wanderer, slicer):

    if type(slicer) is tuple:
        slicer = slice(*slicer)
    start, stop, step = slicer.start, slicer.stop, slicer.step
    if not step is None:
        raise ValueError("Cannot specify step for state.")
    # if not wanderer.initialised:
    #     wanderer.initialise()
    count = wanderer.indices.count._value
    wanCon = ImmutableConfigs(contents = wanderer.configs)
    start = (0 if count is None else count) if start is None else start
    stop = (0 if count is None else count) if stop is None else stop
    start, stop = (_de_comparator(arg) for arg in (start, stop))
    indexlikeStart, indexlikeStop = (
        wanderer.indices._check_indexlike(arg) for arg in (start, stop)
        )
    if indexlikeStart:
        if indexlikeStop or start == 0:
            start = wanCon
        else:
            start = wanderer[wanCon : start]
    elif isinstance(start, WildConfigs):
        if start.indexlike:
            if start.wanderer.hashID == wanderer.hashID:
                start = start.start
    else:
        try:
            start = wanderer.configs.process_configs(start)
        except CannotProcessConfigs:
            raise TypeError("Ran out of ways to create start point.")
    assert isinstance(start, Configs)

    if indexlikeStop:
        if stop == 0:
            raise RedundantWildConfigs
        stop = wanderer.indices.process_endpoint(stop, close = False)
    elif isinstance(stop, Function):
        if not stop.slots == 1:
            raise ValueError("Wrong number of slots on stop comparator.")
    else:
        raise TypeError("Stop must be a Function or convertible to one.")
    assert isinstance(stop, Function)

    return start, stop

class Wanderer(Voyager, Configurable):

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

    @property
    def locality(self):
        return self.configs.id, tuple(i.value for i in self.indices)

    def _configurable_changed_state_hook(self):
        super()._configurable_changed_state_hook()
        self.indices.nullify()

    def _initialise(self, *args, **kwargs):
        self.configs.apply(silent = True)
        super()._initialise(*args, **kwargs)
        self.configs.configured = False

    @_voyager_initialise_if_necessary(post = True)
    def go(self, arg1, arg2 = None):
        if arg2 is None:
            super().go(arg1)
        else:
            start, stop = get_start_stop(self, (arg1, arg2))
            self.configs.set_configs(**start)
            super().go(stop)

    @_voyager_initialise_if_necessary(post = True)
    def _out(self, *args, **kwargs):
        return super()._out(*args, **kwargs)

    def _load(self, arg):
        super()._load(arg)
        if not self.indices.isnull:
            self.configs.configured = False

    def __getitem__(self, arg):
        assert len(self.configs)
        if len(self.configs) == 1:
            return self._wanderer_get_single(arg)
        else:
            return self._wanderer_get_multi(arg)
    def _wanderer_get_single(self, arg):
        raise exceptions.NotYetImplemented
    def _wanderer_get_multi(self, arg):
        if type(arg) is str:
            if not arg in self.configs:
                raise ValueError
            return self[:][arg]
        else:
            if not type(arg) is slice:
                arg = slice(arg)
            start, stop, step = arg.start, arg.stop, arg.step
            try:
                return WildConfigs.get_wild(self, arg)
            except RedundantWildConfigs:
                return ImmutableConfigs(contents = self.configs)

    def __setitem__(self, key, val):
        if isinstance(val, Wanderer):
            val = val[:]
        if isinstance(val, WildConfigs):
            if val.wanderer.hashID == self.hashID:
                if not val.start.id == self.configs.id:
                    self[...] = val.start
                if not self.indices == val.indices:
                    assert self.outputSubKey == val.data.name
                    self.load(val.data)
                    assert self.indices == val.indices
                return
            else:
                val = val[:]
        super().__setitem__(key, val)
        return

    # @property
    # def _promptableKey(self):
    #     # Overrides Promptable property:
    #     return self.configs.contentHash
