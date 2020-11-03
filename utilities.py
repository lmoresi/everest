import math
import numbers
import numpy as np

def prettify_nbytes(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])

def is_numeric(arg):
    try:
        _ = arg + 1
        return True
    except:
        return False

def make_scalar(arg):
    if isinstance(arg, np.ndarray):
        if len(arg.shape):
            if any(i > 1 for i in arg.shape):
                raise ValueError(
                    "Array-like input must have only one entry: shape was ",
                    arg.shape
                    )
            for i in arg.shape:
                arg = arg[i]
        else:
            arg = arg.item()
    else:
        pass
    if not issubclass(type(arg), numbers.Number):
        raise ValueError(arg, type(arg))
    return arg

from collections import OrderedDict
from collections.abc import Sequence, Mapping

def ordered_unpack(keys, arg1, arg2):
    keys = list(keys)
    if arg1 is Ellipsis:
        seqChoice = range(len(keys))
        mapChoice = keys
    elif type(arg1) is str:
        seqChoice = [keys.index(arg1),]
        mapChoice = [arg1,]
    elif type(arg1) is int:
        seqChoice = [arg1,]
        mapChoice = [keys[arg1],]
    elif type(arg1) is tuple:
        if len(set([type(o) for o in arg1])) > 1:
            raise ValueError
        if type(arg1[0]) is str:
            seqFn = lambda arg: keys.index(arg)
            seqChoice = [seqFn(arg) for arg in arg1]
            mapChoice = arg1
        elif type(arg1[0] is int):
            mapFn = lambda arg: keys[arg]
            seqChoice = arg1
            mapChoice = [mapFn(arg) for arg in arg1]
        else:
            raise TypeError
    if isinstance(arg2, Sequence):
        mapDict = OrderedDict((keys[i], arg2[i]) for i in seqChoice)
    elif isinstance(arg2, Mapping):
        mapDict = OrderedDict((k, arg2[k]) for k in mapChoice)
    else:
        mapDict = OrderedDict((keys[i], arg2) for i in seqChoice)
    return mapDict
