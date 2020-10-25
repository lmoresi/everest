import math

import wordhash
w_hash = wordhash.w_hash
from frame.utilities import make_hash, get_hash

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
