from functools import wraps, cached_property
import numbers
import warnings
from collections import OrderedDict
from collections.abc import Iterable as abcIterable
from collections.abc import Iterator as abcIterator
from collections.abc import Sequence
import weakref

from funcy import Fn, NullValueDetected
import wordhash
from ptolemaic import Case
from ptolemaic.frames.producer import LoadFail
from ptolemaic.frames.indexable import NotIndexlike
from ptolemaic.frames import Geometric

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

# class IterableCase(Case):
#     def __getitem__(case, args):
#         if not type(args) is tuple:
#             args = args,
#         if len(args) > 1:
#             raise NotYetImplemented
#         arg = args[0]
#         if type(arg) is slice:
#             return case.Interval(case, arg.start, arg.stop, arg.step)
#         else:
#             return case.Stage(case, arg)

class Iterable(Prompter, Geometric):

    def __init__(self,
            **kwargs
            ):
        super().__init__(**kwargs)

    @property
    def initialised(self):
        return self.indices.iszero
    @property
    def postinitialised(self):
        return self.indices.ispos
    @_iterable_initialise_if_necessary
    def get_storage(self, *args, **kwargs):
        return super().get_storage(*args, **kwargs)

    def _try_load(self, stop, /):
        try: self.load(stop)
        except LoadFail: raise BadStrategy
    def _try_convert(self, stop, /):
        try: return Fn(stop)
        except (ValueError, TypeError): raise BadStrategy
    def _try_index(self, stop, /):
        try: return self.indices.get_index(stop)
        except NotIndexlike: raise BadStrategy
    def _try_strats(self, strats, *args, **kwargs):
        for strat in strats:
            try: return strat(*args, **kwargs)
            except BadStrategy: pass
        raise ExhaustedStrategies("Could not find a strategy to proceed.")

    # REACH
    def reach(self, arg, /, *args, **kwargs):
        self._reach(arg, **kwargs)
        if args:
            self.stride(*args, **kwargs)
    def _reach(self, stop = None, /, **kwargs):
        if stop is None:
            self._reach_end()
        else:
            strats = (
                self._try_load,
                self._reach_index,
                self._reach_fn
                )
            self._try_strats(strats, stop, **kwargs)
    def _reach_end(self, /, **kwargs):
        presentCount = self.index.data
        if presentCount == self.terminus: return None
        stored = self.storage[self.index.name]
        if stored:
            i = max(stored)
            if i != presentCount:
                self.load(i)
            if i == self.terminus: return None
        self.go(None, **kwargs)
    @_iterable_initialise_if_necessary
    def _reach_index(self, stop, /, index = None):
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
    def _reach_fn(self, stop, /, **kwargs):
        stop = self._try_convert(stop)
        try:
            self.load(stop)
        except LoadFail:
            self.reset()
            closed = stop.allclose(self)
            while not closed:
                self.iterate(**kwargs)

    # STRIDE
    def stride(self, /, *args, **kwargs):
        for arg in args:
            self._stride(arg, **kwargs)
    def _stride(self, stop, /, **kwargs):
        try:
            index = self._try_index(stop)
            stop = (index + stop).value
            return self._reach_index(stop, index, **kwargs)
        except BadStrategy:
            pass
        return self._go_fn(stop, **kwargs)

    # GO
    def go(self, /, *args, **kwargs):
        for arg in args:
            self.go(arg, **kwargs)
    def _go(self, stop = None, /, **kwargs):
        if stop is None:
            self._go_indefinite(**kwargs)
        elif issubclass(type(stop), numbers.Integral):
            self._go_integral(stop, **kwargs)
        else:
            strats = (self._go_index, self._go_fn)
            self._try_strats(*strats, stop = stop, **kwargs)
    def _go_indefinite(self, /):
        try:
            while True:
                self.iterate()
        except StopIteration:
            pass
        self.terminus = self.indices[0].value
    def _go_integral(self, stop, /, **kwargs):
        for _ in range(stop):
            self.iterate(**kwargs)
    def _go_index(self, stop, /, index = None, **kwargs):
        index = self._try_index(stop)
        stop = (index + stop).value
        while index < stop:
            self.iterate(**kwargs)
    def _go_fn(self, stop, /, **kwargs):
        stop = self._try_convert(stop)
        stop = stop.allclose(self)
        while not stop:
            self.iterate(**kwargs)

    # RUN
    def run(self, /, *args, **kwargs):
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

    def _setitem(self, keyvals, /):
        super()._setitem(keyvals)
        key, val = next(keyvals)
        if not key is Ellipsis:
            raise ValueError("Iterable set arg must be Ellipsis.")
        try:
            val = tuple(val)
        except TypeError:
            val = val,
        self.reach(*val)

    def _report(self):
        try:
            yield from self.indices._report()
            yield from self.state._report()
        except NullValueDetected:
            yield "null"
    def report(self):
        head = f" \
            FrameInstance '{type(self).__name__}' \
            ({self.instanceHash}): \
            "
        return '\n    '.join((head, *self._report()))

    # def _getitem(self, args, outs):
    #     arg = next(args)
    #     if not type(arg) is slice:
    #         if not type(arg) is tuple:
    #             arg = arg,
    #         arg = slice(*arg)
    #     for _ in self.iterator(arg.start, arg.stop, arg.step):
    #         self.store()
    #     super()._getitem(args, )

# class Stage(State):
#     def __init__(self, case, *args):
#         self.case, self.args = case, args
#     @property
#     def _vars(self):
#         frame = self.case.frame
#         frame.reach(*self.args)
#         return frame.state._vars

# from ._sliceable import BythicCase
# class IterableCase(BythicCase):
#     # def __getitem__(case, key, /):
#     #     case.frame
#     ...


    # def __setitem__(self, key, val):
    #     if not key is Ellipsis:
    #         raise ValueError(
    # "Can only set Iterables with Ellipsis as key.")
    #     if isinstance(val, Stage):
    #         val = val.args
    #     elif not type(val) is tuple:
    #         val = (val,)
    #     self.reach(*val)

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
#         return IntervalIterator(
# self.frame, self.start, self.stop, self.step)
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
#         self.stop = \
            # False if stop is None else self._frame._get_stop_fn(stop)
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
#
# class IterableCase:
#     def __getitem__(case, keys):
#         if not type(keys) is tuple:
#             keys = (keys,)
#         hashID = wordhash.w_hash(tuple((case, *keys)))
#         stage = case.stages.setdefault(hashID, Stage(case, *keys))
#         stage._hashID = hashID
#         return stage
#     @cached_property
#     def frame(case):
#         return case()
#     @property
#     def stages(case):
#         try:
#             return case._stages
#         except AttributeError:
#             case._stages = weakref.WeakValueDictionary()
#             return case._stages
