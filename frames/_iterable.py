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
class BadStrategy(IterableException):
    pass
class ExhaustedStrategies(IterableException):
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

    def _try_load(self, stop, silent = False):
        try: self.load(stop)
        except LoadFail: raise BadStrategy
    def _try_convert(self, stop):
        try: return convert(stop)
        except (ValueError, TypeError): raise BadStrategy
    def _try_index(self, stop):
        try: return self.indices.get_index(stop)
        except NotIndexlike: raise BadStrategy
    def _try_strats(self, *strats, **kwargs):
        for strat in strats:
            try: return strat(**kwargs)
            except BadStrategy: pass
        raise ExhaustedStrategies("Could not find a strategy to proceed.")

    def reach(self, *args, **kwargs):
        if args:
            arg, *args = args
            self._reach(arg, **kwargs)
            if args:
                self.stride(*args, **kwargs)
        else:
            self._reach(**kwargs)
    def _reach(self, stop = IterableEnded, **kwargs):
        if stop is None:
            raise ValueError
        strats = (
            self._reach_end,
            self._try_load,
            self._reach_index,
            self._reach_fn
            )
        self._try_strats(*strats, stop = stop, **kwargs)
    def _reach_end(self, stop = IterableEnded, silent = True, **kwargs):
        if not type(stop) is type:
            raise BadStrategy
        if not issubclass(stop, StopIteration):
            raise BadStrategy
        stored = self.indices.stored[self.indices[0].name]
        if stored:
            i = max(stored)
            if i != self.indices[0]:
                self.load(i)
        self.go(silent = silent, **kwargs)
    @_iterable_initialise_if_necessary(post = True)
    def _reach_index(self, stop, index = None, silent = False):
        if index is None:
            index = self._try_index(stop)
        if index == stop:
            if silent: return
            else: raise RedundantIterate
        stored = self.indices.stored[index.name]
        try: latest = sorted(i for i in stored if i < index)[-1]
        except IndexError: latest = None
        if not latest is None:
            return self.load(latest)
        else:
            if index > stop:
                self.reset()
        stop = index >= stop
        while not stop:
            self.iterate(silent = silent)
    @_iterable_initialise_if_necessary(post = True)
    def _reach_fn(self, stop, **kwargs):
        stop = self._try_convert(stop)
        try:
            self.load(stop)
        except LoadFail:
            self.reset()
            closed = stop.allclose(self)
            while not closed:
                self.iterate(**kwargs)

    def stride(self, *args, **kwargs):
        if args:
            for arg in args:
                self._stride(arg, **kwargs)
        else:
            self._stride(**kwargs)
    def _stride(self, stop = IterableEnded, **kwargs):
        if stop is None:
            raise ValueError
        strats = (self._reach_end, self._stride_index, self._stride_fn)
        self._try_strats(*strats, stop = stop, **kwargs)
    @_iterable_initialise_if_necessary(post = True)
    def _stride_index(self, stop, **kwargs):
        index = self._try_index(stop)
        stop = (index + stop).value
        self._reach_index(stop, index = index, **kwargs)
    @_iterable_initialise_if_necessary(post = True)
    def _stride_fn(self, stop, **kwargs):
        stop = self._try_convert(stop)
        ind, val = self.indices.get_now()
        stop = (ind >= val) & stop
        try:
            self._try_load(stop)
        except BadStrategy:
            closed = stop.allclose(self)
            while not closed:
                self.iterate(**kwargs)

    @_iterable_initialise_if_necessary(post = True)
    def go(self, *args, **kwargs):
        if args:
            *args, arg = args
            if args:
                self.stride(*args, **kwargs)
            self._go(arg)
        else:
            self._go(**kwargs)
    def _go(self, stop = None, **kwargs):
        if stop is None:
            self._go_indefinite(**kwargs)
        elif issubclass(type(stop), numbers.Integral):
            self._go_integral(stop, **kwargs)
        else:
            strats = (self._go_index, self._go_fn)
            self._try_strats(*strats, stop = stop, **kwargs)
    def _go_indefinite(self, silent = True):
        if not silent:
            warnings.warn("Running indefinitely - did you intend this?")
        while True:
            try:
                self.iterate()
            except IterableEnded:
                if silent:
                    return
                else:
                    raise IterableEnded
    def _go_integral(self, stop, **kwargs):
        for _ in range(stop):
            self.iterate(**kwargs)
    def _go_index(self, stop, index = None, **kwargs):
        if index is None:
            index = self._try_index(stop)
        stop += index.value if not self.indices.isnull else 0
        while index < stop:
            self.iterate(**kwargs)
    def _go_fn(self, stop, **kwargs):
        stop = self._try_convert(stop)
        stop = stop.allclose(self)
        while not stop:
            self.iterate(**kwargs)

    @_iterable_initialise_if_necessary()
    def run(self, *args, **kwargs):
        self.go(*args, **kwargs)

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