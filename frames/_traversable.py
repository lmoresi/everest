import numpy as np
from functools import wraps

from funcy import Function

from ._iterable import Iterable
from ._stateful import State
from ._configurable import Configurable, Configs

from ..exceptions import *
class TraversableException(EverestException):
    pass
class RedundantState(TraversableException):
    pass

def _traversable_abs_steer(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if len(args):
            config, *args = args
            self[...] = config
        return func(self, *args, **kwargs)
    return wrapper

# class TraversableCase:
#     def __getitem__(case, key):
#         if type(key) is tuple:
#             return super().__getitem__(*key)
#         elif type(key) is slice:
#             return Interval(case, key)
#         else:
#             return Stage(case, key)

class Traversable(Iterable, Configurable):

    # @classmethod
    # def _casebases(cls):
    #     for c in super()._casebases(): yield c
    #     yield ProducerCase

    def __init__(self,
            **kwargs
            ):
        super().__init__(**kwargs)

    def _configurable_changed_state_hook(self):
        super()._configurable_changed_state_hook()
        self.indices.nullify()

    def _initialise(self, *args, **kwargs):
        self.configs.apply()
        super()._initialise(*args, **kwargs)

    @_traversable_abs_steer
    def reach(self, *args, **kwargs):
        return super().reach(*args, **kwargs)
    @_traversable_abs_steer
    def run(self, *args, **kwargs):
        return super().run(*args, **kwargs)

    # @_iterable_initialise_if_necessary(post = True)
    # def _out(self, *args, **kwargs):
    #     return super()._out(*args, **kwargs)

# class Locality


    # def _load(self, arg):
    #     super()._load(arg)
    #     if not self.indices.isnull:
    #         self.configs.configured = False

    # @_iterable_initialise_if_necessary(post = True)
    # def go(self, arg1, arg2 = None):
    #     if arg2 is None:
    #         super().goto(arg1)
    #     else:
    #         start, stop = get_start_stop(self, (arg1, arg2))
    #         self.configs[...] = start
    #         super().goto(stop)

    # def __getitem__(self, arg):
    #     assert len(self.configs)
    #     if len(self.configs) == 1:
    #         return self._traversable_get_single(arg)
    #     else:
    #         return self._traversable_get_multi(arg)
    # def _traversable_get_single(self, arg):
    #     raise exceptions.NotYetImplemented
    # def _traversable_get_multi(self, arg):
    #     if type(arg) is str:
    #         if not arg in self.configs:
    #             raise ValueError
    #         return self[:][arg]
    #     else:
    #         if not type(arg) is slice:
    #             arg = slice(arg)
    #         start, stop, step = arg.start, arg.stop, arg.step
    #         try:
    #             return WildConfigs.get_wild(self, arg)
    #         except RedundantState:
    #             return Configs(contents = self.configs)

    # def _traversable_setitem__(self, key, val):
    #     if isinstance(val, Traversable):
    #         val = val[:]
    #     if isinstance(val, WildConfigs):
    #         if val.traversable.hashID == self.hashID:
    #             if not val.start.id == self.configs.id:
    #                 self.configs[...] = val.start
    #             if not self.indices == val.indices:
    #                 assert self.outputSubKey == val.data.name
    #                 self.load(val.data)
    #                 assert self.indices == val.indices
    #             return
    #         else:
    #             val = val[:]
    #     super().__setitem__(key, val)
    #     return


# def _spec_context_wrap(func):
#     @wraps(func)
#     def wrapper(specState, *args, **kwargs):
#         if not specState._computed:
#             specState._compute()
#         return func(specState, *args, **kwargs)
#     return wrapper
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
#
# def _de_comparator(obj):
#     if isinstance(obj, Function) and hasattr(obj, 'index'):
#         return obj.index
#     else:
#         return obj
# #
# def get_start_stop(traversable, slicer):
#
#     if type(slicer) is tuple:
#         slicer = slice(*slicer)
#     start, stop, step = slicer.start, slicer.stop, slicer.step
#     if not step is None:
#         raise ValueError("Cannot specify step for state.")
#     # if not traversable.initialised:
#     #     traversable.initialise()
#     count = traversable.indices['count'].value
#     wanCon = Configs(traversable.configs)
#     start = (0 if count is None else count) if start is None else start
#     stop = (0 if count is None else count) if stop is None else stop
#     start, stop = (_de_comparator(arg) for arg in (start, stop))
#     indexlikeStart, indexlikeStop = (
#         traversable.indices._check_indexlike(arg) for arg in (start, stop)
#         )
#     if indexlikeStart:
#         if indexlikeStop or start == 0:
#             start = wanCon
#         else:
#             start = traversable[wanCon : start]
#     elif isinstance(start, SpecState):
#         if start.indexlike:
#             if start.traversable.hashID == traversable.hashID:
#                 start = start.start
#     else:
#         startConfig = traversable.configs.copy()
#         startConfig[...] = start
#         start = startConfig
#     if indexlikeStop:
#         if stop == 0:
#             raise RedundantState
#         # stop = traversable.indices.process_endpoint(stop, close = False)
#     elif isinstance(stop, Function):
#         if not stop.slots == 1:
#             raise ValueError(
#                 "Wrong number of slots on stop comparator: ",
#                 stop.slots
#                 )
#     else:
#         raise TypeError(
#             "Stop must be a Function or convertible to one, not ",
#             stop, type(stop)
#             )
#     assert isinstance(start, State)
#     assert isinstance(stop, Function)
#     return start, stop
