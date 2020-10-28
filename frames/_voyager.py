from functools import wraps

from funcy import Function

from ._stateful import Stateful
from ._counter import Counter
from ._cycler import Cycler
from ._producer import LoadFail, _producer_update_outs
from ._prompter import Prompter, _prompter_prompt_all

from ..exceptions import *
class VoyagerException(EverestException):
    pass
class VoyagerMissingAsset(MissingAsset, VoyagerException):
    pass
class VoyagerAlreadyInitialised(VoyagerException):
    pass
class VoyagerNotInitialised(VoyagerException):
    pass

def _voyager_initialise_if_necessary(post = False):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if post:
                cond = self.initialised or self.postinitialised
            else:
                cond = self.initialised
            if not cond:
                self.initialise()
            return func(self, *args, **kwargs)
        return wrapper
    return decorator
def _voyager_changed_state(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        pc = (i.data for i in self.indices)
        out = func(self, *args, **kwargs)
        nc = (i.data for i in self.indices)
        if nc != pc:
            self._voyager_changed_state_hook()
        return out
    return wrapper

class Voyager(Stateful, Cycler, Counter, Prompter):

    def __init__(self,
            **kwargs
            ):

        self.baselines = dict()

        super().__init__(**kwargs)

    def initialise(self, silent = False):
        if self.initialised:
            if silent:
                pass
            else:
                raise VoyagerAlreadyInitialised
        else:
            self._initialise()
            assert self.initialised
    def _initialise(self):
        self.indices.zero()
        self._voyager_changed_state_hook()
    @property
    def initialised(self):
        return self.indices.iszero
    @property
    def postinitialised(self):
        return self.indices.ispos
    def reset(self, silent = True):
        self.initialise(silent = silent)
    @_producer_update_outs
    @_prompter_prompt_all
    def _voyager_changed_state_hook(self):
        pass

    @_voyager_initialise_if_necessary(post = True)
    def iterate(self, n = 1, silent = True):
        for i in range(n):
            self._iterate()
    @_voyager_changed_state
    def _iterate(self):
        self.indices.count.value += 1

    @_voyager_initialise_if_necessary(post = True)
    def go(self, stop):
        if type(stop) is bool:
            self._go()
            return None
        try:
            # self.load(stop)
            raise LoadFail
        except LoadFail:
            if not isinstance(stop, Function):
                stop = self.indices.process_endpoint(stop, close = False)
            if self.indices.isnull:
                self.initialise()
            slots = stop.slots
            if slots == 1:
                boolean = stop.close(self)
            elif slots == 0:
                boolean = stop
            else:
                raise ValueError("Too many slots on comparator.")
            self.reset()
            if boolean:
                raise Exception("Condition already met.")
            self._go(boolean)
    def _go(self, stop = False):
        while not stop:
            self.iterate()

    def _cycle(self):
        super()._cycle()
        self.iterate()

    @_voyager_initialise_if_necessary(post = True)
    def _out(self):
        return super()._out()
    @_voyager_changed_state
    def _load(self, arg):
        if self.indices._check_indexlike(arg):
            if arg == 0:
                try:
                    return super()._load(arg)
                except IndexerLoadFail:
                    self.initialise(silent = True)
        return super()._load(arg)
