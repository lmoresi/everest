import weakref
from collections import OrderedDict

class Freq(OrderedDict):

    def __init__(self):
        pass

    def __getitem__(self, key):
        out = None
        todels = []
        for weakkey in self.keys():
            resolved = weakkey()
            if resolved is key:
                out = super().__getitem__(weakkey)
            elif resolved is None:
                todels.append(weakkey)
        for todel in todels:
            super().__delitem__(todel)
        if out is None:
            raise KeyError
        return out
    def __setitem__(self, key, item):
        super().__setitem__(weakref.ref(key), item)
    def __delitem__(self, key):
        for weakkey in self.keys():
            resolved = weakkey()
            if resolved is key:
                super().__delitem__(weakkey)
            elif resolved is None:
                todels.append(weakkey)
        for todel in todels:
            super().__delitem__(todel)

    def __bool__(self):
        return any(self.values())
