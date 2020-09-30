from types import FunctionType
import operator

from .pyklet import Pyklet

class Comparator(Pyklet):

    def __init__(self,
            *props,
            op : (str, FunctionType) = bool,
            asList = False
            ):

        if type(op) is str:
            op = operator.__dict__[op]

        super().__init__(*props, op = op, asList = asList)

        self.props, self.op, self.asList = props, op, asList

    def __call__(self, *objs):

        props = self.props
        if len(objs) > len(self.props):
            props = self.pack_list(props, objs)

        targets = [
            self._expose_property(o, p)
                for o, p in zip(objs, props)
            ]

        if self.asList:
            return self.op(targets)
        else:
            return self.op(*targets)

    @staticmethod
    def pack_list(list1, list2):

        return [*list1, *[None for i in range(len(list2) - len(list1))]]

    @staticmethod
    def _expose_property(obj, props):

        if props is None:
            return obj
        else:
            props = props.split('/')
            for prop in props:
                obj = getattr(obj, prop)
            return obj