from functools import wraps
import numbers
import warnings

from funcy import Fn, convert, NullValueDetected

from ._stateful import Stateful, State
from ._indexable import Indexable, NotIndexlike
from ._producer import LoadFail, _producer_update_outs
from ._prompter import Prompter, _prompter_prompt_all

from ..exceptions import *
class IterableException(EverestException):
    pass
class IterableMissingAsset(MissingAsset, IterableException):
    pass
class IterableAlreadyInitialised(IterableException):
    pass
class IterableNotInitialised(IterableException):
    pass
class RedundantIterate(IterableException):
    pass
class IterableEnded(StopIteration, IterableException):
    pass

def _iterable_initialise_if_necessary(post = False):
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
def _iterable_changed_state(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        pc = (i.data for i in self.indices)
        out = func(self, *args, **kwargs)
        nc = (i.data for i in self.indices)
        if nc != pc:
            self._iterable_changed_state_hook()
        return out
    return wrapper

class Iterable(Stateful, Indexable, Prompter):

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
                raise IterableAlreadyInitialised
        else:
            self._initialise()
            assert self.initialised
    def _initialise(self):
        self.indices.zero()
        self._iterable_changed_state_hook()
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
    def _iterable_changed_state_hook(self):
        pass

    @property
    def stop(self):
        return self._stop()
    def _stop(self):
        return False
    def _check_stop(self, silent = False):
        if self.stop:
            if silent:
                return True
            raise IterableEnded
        return False

    def iterate(self, silent = False):
        if not self._check_stop(silent):
            self._iterate()
    def _iterate(self):
        self.indices['count'] += 1
        self._iterable_changed_state_hook()

    @_iterable_initialise_if_necessary(post = True)


    @_iterable_initialise_if_necessary(post = True)
    def goto(self, stop, silent = False):
        try:
            index = self.indices.get_index(stop)
            if index == stop:
                if silent:
                    return
                raise RedundantIterate
        except NotIndexlike:
            index = None
        try:
            self.load(stop)
            return
        except LoadFail:
            pass
        if index is None:
            self.reset()
            stop = convert(stop)
        else:
            stored = self.indices.stored[index.name]
            try:
                latest = sorted(i for i in stored if i < index)[-1]
                self.load(latest)
            except IndexError:
                self.reset()
            stop = index >= stop
        stop = stop.allclose(self)
        while not stop:
            self.iterate(silent = silent)

    def run(self):
        self.go(silent = True)
    @_iterable_initialise_if_necessary(post = True)
    def go(self, stop = None, silent = False):
        if stop is None:
            self._go_indefinite(silent = silent)
        elif issubclass(type(stop), numbers.Integral):
            self._go_integral(stop, silent = silent)
        else:
            try:
                self._go_index(stop, silent = silent)
            except NotIndexlike:
                if isinstance(stop, Fn):
                    self._go_fn(stop, silent = silent)
                else:
                    raise ValueError
    def _go_indefinite(self, silent = False):
        if not silent:
            warnings.warn("Running indefinitely - did you intend this?")
        while True:
            try:
                self.iterate()
            except IterableEnded:
                if silent:
                    return
                raise IterableEnded
    def _go_integral(self, stop, silent = False):
        for _ in range(stop):
            self.iterate(silent = silent)
    def _go_index(self, stop, silent = False):
        index = self.indices.get_index(stop)
        stop += index.value if not self.indices.isnull else 0
        while index < stop:
            self.iterate(silent = silent)
    def _go_fn(self, stop, silent = False):
        stop = stop.allclose(self)
        while not stop:
            self.iterate(silent = silent)

    @_iterable_initialise_if_necessary(post = True)
    def _out(self):
        return super()._out()
    @_iterable_changed_state
    def _load(self, arg):
        if self.indices._check_indexlike(arg):
            if arg == 0:
                try:
                    return super()._load(arg)
                except IndexableLoadFail:
                    self.initialise(silent = True)
        return super()._load(arg)

# class Locality(State):
#     def __init__(self, iterable, locale):
#         self.iterab

#     def _process_get(self, arg):
#         if isinstance(arg, slice):
#             self._process_get_slice(arg)
#         else:
#             self._process_get_index(arg)
#     def _process_get_slice(self, arg):
#         *bounds, step = slicer.start, slicer.stop, slicer.step
#         if not step is None:
#             raise NotYetImplemented
#         try:
#             index = self.indices.values()[0].value
#         except NullValueDetected:
#             index = 0
#         start, stop = bounds = (index if s is None else s for s in bounds)
#         checkFn = self.indices._check_indexlike
#         indexlikeStart, indexlikeStop = (checkFn(arg) for arg in bounds)
#         raise NotYetImplemented
#     def _process_get_index(self, arg):
#         return
#
# class Locality(State):
#     def __init__(self, system, index):
#         if not isinstance(system, Iterator):
#             raise TypeError
#         self.system = system.copy()
#         self.system._outs = system._outs
#         self.index = index
#     def _vars(self):
#         self.system.goto(self.index)
#

# class SpecState(State):
#     def __init__(self, traversable, slicer):
#         self.start, self.stop = get_start_stop(traversable, slicer)
#         self.indexlike = hasattr(self.stop, 'index')
#         self._computed = False
#         self.traversable = traversable.copy()
#         self.traversable._outs = traversable._outs
#         super().__init__()
#     def _compute(self):
#         assert not self._computed
#         self.traversable.goto(self.start, self.stop)
#         self._computed = True
#     @property
#     def _vars(self):
#         return self._traversable_get_vars()
#     @_spec_context_wrap
#     def _traversable_get_vars(self):
#         return self.traversable.state.vars
