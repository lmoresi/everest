from types import FunctionType

from ._cycler import Cycler
from ._condition import Condition
from ..exceptions import EverestException

# class TaskPrerequisiteNotMetError(EverestException):
#     '''The prerequisite to commence this task \
# has not been met yet.'''
#     pass
# class TaskStopMetError(EverestException):
#     '''The task has been completed.'''
#     pass

class Task(Condition, Cycler):

    def __init__(
            self,
            _task_in : = None,
            _task_stopPartial = None,
            **kwargs
            ):

        super().__init__()

        # Cycler attributes:
        if isinstance(_task_in, Task):
            cycler = _task_in()
        else:
            cycler = _task_in
        if not isinstance(cycler, Cycler):
            raise TypeError
        def cycle():
            while not self: cycler()
            return cycler
        self._cycle_fns.append(cycle)

        # Condition attributes:
        condition = _task_stopPartial.build(cycler)
        self._bool_fns.append(lambda: _task_boolFn(cycler))
