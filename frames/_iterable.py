from functools import wraps
import numbers
import warnings
from collections import OrderedDict
from collections.abc import Iterable as abcIterable
from collections.abc import Iterator as abcIterator
import weakref

from funcy import Fn, NullValueDetected
import wordhash

from . import Frame
from ._stateful import Stateful, State
from ._indexable import Indexable, NotIndexlike, IndexableLoadFail
from ._producer import LoadFail
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

def _iterable_initialise_if_necessary(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except NullValueDetected:
            self.initialise()
            return func(self, *args, **kwargs)
    return wrapper

class Stage(State):
    def __init__(self, case, *args):
        self.case, self.args = case, args
    @property
    def frame(self):
        self.case.frame.reach(*self.args)
        return self.case.frame
    @property
    def _vars(self):
        return self.frame.state._vars
    @property
    def hashID(self):
        return self._hashID

class IterableCase:
    def __getitem__(case, keys):
        if not type(keys) is tuple:
            keys = (keys,)
        hashID = wordhash.w_hash(tuple((case, *keys)))
        stage = case.stages.setdefault(hashID, Stage(case, *keys))
        stage._hashID = hashID
        return stage
    @property
    def frame(case):
        try:
            return case._frame
        except AttributeError:
            case._frame = case()
            return case._frame

    @property
    def stages(case):
        try:
            return case._stages
        except AttributeError:
            case._stages = weakref.WeakValueDictionary()
            return case._stages
        # if type(key) is slice:
        #     return Interval(case, key)
        # elif type(key) is tuple:
        #     return Stage(case, *key)
        # else:
        #     return Stage(case, key)

# class SpecFrame:
#     _preframes = weakref.WeakValueDictionary()
#     def __init__(self, case, *targs):
#         self.case = case
#         self._frame = self._preframes.setdefault(case.hashID, case())
#         self.targs = targs
#         super().__init__()
#     def compute(self):
#         self._frame.reach(*self.targs)
#         self._frame.store()
#     def _compute_wrap(func):
#         @wraps(func)
#         def wrapper(self, *args, **kwargs):
#             self.compute()
#             return func(self, *args, **kwargs)
#         return wrapper
#     @property
#     @_compute_wrap
#     def frame(self):
#         return self._frame
#     @property
#     @_compute_wrap
#     def index(self):
#         return self._index
#
# class Stage(SpecFrame, State):
#     def __init__(self, *targs):
#         super().__init__(*targs)
#     @property
#     def _vars(self):
#         return self.frame.state.vars
#     def __repr__(self):
#         content = [self._frame.hashID, *(repr(t) for t in self.targs)]
#         return type(self).__name__ + '(' + ', '.join(content) + ')'
#
# class Interval(abcIterable):
#     def __init__(self, case, slicer):
#         if not type(slicer) is slice:
#             slicer = slice(*slicer)
#         self.start, self.stop, self.step = \
#             slicer.start, slicer.stop, slicer.step
#         self.frame = SpecFrame._get_local_frame(case)
#         self.frame, self.slicer = frame, slicer
#         super().__init__()
#     def __iter__(self):
#         return IntervalIterator(self.frame, self.start, self.stop, self.step)
#     # def __getitem__(self, key):
#     #     raise Exception
#     def __repr__(self):
#         name = type(self).__name__
#         content = self.frame.hashID, self.slicer
#         return name + '(' + ', '.join(repr(o) for o in content) + ')'
#
# class IntervalIterator(SpecFrame, abcIterator):
#     def __init__(self, frame, start, stop, step):
#         self.start = start
#         self.step = 1 if step is None else step
#         super().__init__(frame, self.start)
#         self.stop = False if stop is None else self._frame._get_stop_fn(stop)
#         self.i = 0
#         self.compute()
#     def __iter__(self):
#         return self
#     def __next__(self):
#         if self.stop:
#             raise StopIteration
#         else:
#             self._frame.stride(self.step)
#             self.i += 1
#             return self._frame[None]

class Iterable(Indexable, Prompter, Stateful):

    @classmethod
    def _helperClasses(cls):
        d = super()._helperClasses()
        d['Case'][0].append(IterableCase)
        return d

    def __init__(self,
            **kwargs
            ):
        self.terminus = None
        super().__init__(**kwargs)
        self._iterCount = self.indices[0]
        for var in self.state._vars.values():
            var.index = self._iterCount

    def initialise(self):
        if self.initialised: raise IterableAlreadyInitialised
        self._initialise()
    def _initialise(self):
        self.indices.zero()
    @property
    def initialised(self):
        return self.indices.iszero
    @property
    def postinitialised(self):
        return self.indices.ispos
    def reset(self):
        try: self.initialise()
        except IterableAlreadyInitialised: pass
    @_iterable_initialise_if_necessary
    def _get_storage(self, *args, **kwargs):
        return super()._get_storage(*args, **kwargs)

    # ITERATE
    def iterate(self):
        try:
            self._iterate()
        except (TypeError, NullValueDetected):
            self.initialise()
            self._iterate()
    def _iterate(self):
        self._iterCount.data += 1

    def _try_load(self, stop):
        try: self.load(stop)
        except LoadFail: raise BadStrategy
    def _try_convert(self, stop):
        try: return Fn(stop)
        except (ValueError, TypeError): raise BadStrategy
    def _try_index(self, stop):
        try: return self.indices.get_index(stop)
        except NotIndexlike: raise BadStrategy
    def _try_strats(self, *strats, **kwargs):
        for strat in strats:
            try: return strat(**kwargs)
            except BadStrategy: pass
        raise ExhaustedStrategies("Could not find a strategy to proceed.")
    def _get_stop_fn(self, stop):
        if stop is None:
            raise ValueError(stop)
        try:
            index = self._try_index(stop)
            return index >= stop
        except BadStrategy: pass
        try:
            return self._try_convert(stop).allclose(self)
        except BadStrategy: pass
        raise ExhaustedStrategies

    # REACH
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
    def _reach_end(self, stop = IterableEnded, **kwargs):
        try:
            if not issubclass(stop, StopIteration):
                raise BadStrategy
        except TypeError:
            raise BadStrategy
        presentCount = self._iterCount.data
        if presentCount == self.terminus: return None
        stored = self.storage[self._iterCount.name]
        if stored:
            i = max(stored)
            if i != presentCount:
                self.load(i)
            if i == self.terminus: return None
        self.go(**kwargs)
    @_iterable_initialise_if_necessary
    def _reach_index(self, stop, index = None):
        if index is None:
            index = self._try_index(stop)
        if index == stop:
            raise StopIteration
        self.storage.tidy()
        stored = self.storage[index.name]
        try:
            stored = stored[stored <= stop].max()
            self.load_index(stored)
            if stored == stop:
                return
        except (IndexError, ValueError):
            if index.value > stop:
                self.reset()
        stop = index >= stop
        while not stop:
            self.iterate()
    def _reach_fn(self, stop, **kwargs):
        stop = self._try_convert(stop)
        try:
            self.load(stop)
        except LoadFail:
            self.reset()
            closed = stop.allclose(self)
            while not closed:
                self.iterate(**kwargs)

    # STRIDE
    def stride(self, *args, **kwargs):
        if args:
            for arg in args:
                self._stride(arg, **kwargs)
        else:
            self._stride(**kwargs)
    def _stride(self, stop = IterableEnded, **kwargs):
        try:
            self.load(stop)
        except LoadFail:
            pass
        try:
            index = self._try_index(stop)
            stop = (index + stop).value
            return self._reach_index(stop, index)
        except BadStrategy:
            pass
        return self._go_fn(stop)

    # GO
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
    def _go_indefinite(self):
        try:
            while True:
                self.iterate()
        except StopIteration:
            pass
        self.terminus = self.indices[0].value
    def _go_integral(self, stop, **kwargs):
        for _ in range(stop):
            self.iterate(**kwargs)
    def _go_index(self, stop, index = None, **kwargs):
        index = self._try_index(stop)
        stop = (index + stop).value
        while index < stop:
            self.iterate(**kwargs)
    def _go_fn(self, stop, **kwargs):
        stop = self._try_convert(stop)
        stop = stop.allclose(self)
        while not stop:
            self.iterate(**kwargs)

    # RUN
    def run(self, *args, **kwargs):
        self.reset()
        self.go(*args, **kwargs)

    def _process_loaded(self, *args, **kwargs):
        return super()._process_loaded(*args, **kwargs)
    def _load_out(self, arg):
        if type(arg) is type:
            if issubclass(arg, StopIteration):
                if self.terminus is None:
                    raise LoadFail
                return self.load_index(self.terminus)
        return super()._load_out(arg)

    def __setitem__(self, key, val):
        if not key is Ellipsis:
            raise ValueError("Can only set Iterables with Ellipsis as key.")
        if isinstance(val, Stage):
            val = val.targs
        elif not type(val) is tuple:
            val = (val,)
        self.reach(*val)

    #
    #     if stop is None:
    #         raise ValueError
    #     strats = (self._reach_end, self._stride_index, self._stride_fn)
    #     self._try_strats(*strats, stop = stop, **kwargs)
    # # @_iterable_initialise_if_necessary(post = True)
    # def _stride_index(self, stop, **kwargs):
    #     try:
    #         self._try_load(stop)
    #     except BadStra
    #     index = self._try_index(stop)
    #     stop = (index + stop).value
    #     while index < stop:
    #         self.iterate(**kwargs)
    # # @_iterable_initialise_if_necessary(post = True)
    # def _stride_fn(self, stop, **kwargs):
    #     stop = self._try_convert(stop)
    #     ind, val = self.indices.get_now()
    #     stop = (ind >= val) & stop
    #     try:
    #         self._try_load(stop)
    #     except BadStrategy:
    #         closed = stop.allclose(self)
    #         while not closed:
    #             self.iterate(**kwargs)
