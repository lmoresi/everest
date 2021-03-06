from functools import wraps
from contextlib import contextmanager
import weakref
from collections import OrderedDict

from . import Built
from ._producer import Producer, Outs
from ._observable import Observable

from ..utilities import Grouper

from ..exceptions import EverestException
class ObserverError(EverestException):
    '''An error has emerged related to the Observer class.'''
class ObserverInputError(ObserverError):
    '''Observer subjects must be instances of Observable class.'''
class AlreadyAttachedError(ObserverError):
    '''Observer is already attached to that subject.'''
class NotAttachedError(ObserverError):
    '''Observer is not attached to a subject yet.'''
class NoObservables(ObserverError):
    '''Subject has no observables; it may need to be initialised first.'''

def _attached(func):
    @wraps(func)
    def wrapper(self, *args, silent = False, **kwargs):
        if self.subject is None and not silent:
            raise NotAttachedError
        return func(self, *args, **kwargs)
    return wrapper
def _unattached(func):
    @wraps(func)
    def wrapper(self, *args, silent = False, **kwargs):
        if not self.subject is None and not silent:
            raise AlreadyAttachedError
        return func(self, *args, **kwargs)
    return wrapper

class Observer(Built):

    def __init__(self,
            **kwargs
            ):

        self.subject = None
        self._obsConstruct = None
        self.constructs = weakref.WeakKeyDictionary()
        self.outs = None

        super().__init__(**kwargs)

    @_unattached
    def attach(self, subject):
        if not isinstance(subject, Observable):
            raise TypeError(
                "Observee must be an instance of the Observable class."
                )
        self.subject = subject
        try:
            observer = self.constructs[self.subject]
        except KeyError:
            observer = self.observer_construct(self.subject)
            self.constructs[self.subject] = observer
        self.subject._observer = self
        self.subject.observers[self.hashID] = self
        self.outs = self.subject.outs
    @_attached
    def detach(self, subject):
        self.subject._observer = None
        self.subject = None
        self.observer = None
        self.outs = None

    @contextmanager
    def observe(self, subject):
        self.attach(subject)
        try:
            yield
        finally:
            self.detach(subject)
    def __call__(self, subject):
        return self.observe(subject)

    def register(self, subject):
        with self(subject):
            pass

    @_attached
    def evaluate(self):
        return self.obsConstruct.evaluate()

    @_attached
    def _obs_save(self):
        self.subject.writeouts.add(self, 'observer')

    @property
    @_attached
    def obsConstruct(self):
        if self._obsConstruct is None:
            try:
                self._obsConstruct = self.constructs[self.subject]
                if self._obsConstruct is None:
                    raise KeyError
            except KeyError:
                self._obsConstruct = self.observer_construct(self.subject)
                self.constructs[self.subject] = self._obsConstruct
        return self._obsConstruct

    def observer_construct(self, subject):
        observer = self._observer_construct(subject.observables)
        return observer
    def _observer_construct(self, observables):
        return Grouper({})

    # def _prompt(self, prompter):
    #     # Overrides Promptable _prompt method:
    #     if self.subject is None:
    #         with self.attach(prompter):
    #             super()._prompt(prompter)
    #     elif prompter is self.subject:
    #         super()._prompt(prompter)
    #     else:
    #         raise AlreadyAttachedError
