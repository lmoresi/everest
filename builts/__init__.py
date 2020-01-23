import numpy as np
import os
import importlib
import h5py
import time
import hashlib
import weakref

from .. import utilities
from .. import disk
from .. import mpi
from .. import wordhash

BUILTS = dict()
BUFFERSIZE = 2 ** 30

def buffersize_exceeded():
    nbytes = 0
    for builtID, builtRef in sorted(BUILTS.items()):
        built = builtRef()
        if not built is None:
            nbytes += built.nbytes
    return nbytes > BUFFERSIZE

def get(hashID):
    gotbuilt = BUILTS[hashID]()
    if isinstance(gotbuilt, Built):
        return gotbuilt
    else:
        del BUILTS[hashID]
        raise KeyError

def _load(hashID, name, path = ''):
    framepath = os.path.join(os.path.abspath(path), name + '.frm')
    is_constructor = False
    if mpi.rank == 0:
        with h5py.File(framepath, mode = 'r') as h5file:
            h5group = h5file[hashID]
            if not 'constructor' in h5group.attrs:
                is_constructor = True
    is_constructor = mpi.comm.bcast(is_constructor, root = 0)
    if is_constructor:
        script = None
        if mpi.rank == 0:
            with h5py.File(framepath, mode = 'r') as h5file:
                h5group = h5file[hashID]
                script = h5group['inputs'].attrs['script']
        script = mpi.comm.bcast(script, root = 0)
        loadedBuilt = Constructor(script = script)
    else:
        constructorID = None
        inputs = {}
        subBuiltIDs = {}
        if mpi.rank == 0:
            with h5py.File(framepath, mode = 'r') as h5file:
                h5group = h5file[hashID]
                constructorID = h5file[h5group.attrs['constructor']].name
                inputsGroup = h5group['inputs']
                for key, val in inputsGroup.attrs.items():
                    if type(val) is h5py.Reference:
                        subBuiltIDs[key] = h5file[val].name
                    else:
                        inputs[key] = np.array(val).item()
        constructorID = mpi.comm.bcast(constructorID, root = 0)
        inputs = mpi.comm.bcast(inputs, root = 0)
        subBuiltIDs = mpi.comm.bcast(subBuiltIDs, root = 0)
        for key, val in sorted(subBuiltIDs.items()):
            inputs[key] = load(subBuiltIDs[key], name, path)
        constructor = load(constructorID, name, path)
        loadedBuilt = constructor(**inputs)
    return loadedBuilt

def load(hashID, name, path = ''):
    try:
        loadedBuilt = get(hashID)
    except KeyError:
        loadedBuilt = _load(hashID, name, path)
    loadedBuilt.anchor(name, path)
    return loadedBuilt

def make_hash(obj):
    if isinstance(obj, Built):
        hashVal = obj.instanceHash
    elif type(obj) is dict:
        hashVal = make_hash(sorted(obj.items()))
    elif type(obj) is list or type(obj) is tuple:
        hashList = [make_hash(subObj) for subObj in obj]
        hashVal = make_hash(str(hashList))
    elif isinstance(obj, np.generic):
        hashVal = make_hash(np.asscalar(obj))
    else:
        strObj = str(obj)
        hexID = hashlib.md5(strObj.encode()).hexdigest()
        hashVal = int(hexID, 16)
    return hashVal

class MetaBuilt(type):
    def __call__(cls, **inputs):
        defaultInps = utilities.get_default_kwargs(cls.__init__)
        inputs = {**defaultInps, **inputs}
        cls._process_inputs(inputs)
        if cls is Constructor:
            cls.typeHash = 0
            obj = cls.__new__(cls, inputs)
        else:
            constructor = Constructor(script = cls)
            obj = constructor(**inputs)
        return obj

class Built(metaclass = MetaBuilt):

    h5file = None
    h5filename = None

    species = genus = 'anon'
    inputs = dict()
    meta = dict()
    nbytes = 0

    @staticmethod
    def _process_inputs(inputs):
        pass

    def __new__(cls, inputs):
        inputsHash = make_hash(inputs)
        instanceHash = make_hash((cls.typeHash, inputsHash))
        hashID = wordhash.get_random_phrase(instanceHash)
        try:
            obj = get(hashID)
        except KeyError:
            obj = super().__new__(cls)
            obj.inputs = inputs
            obj.inputsHash = inputsHash
            obj.instanceHash = instanceHash
            obj.hashID = hashID
            obj.__init__(**inputs)
        return obj

    def __init__(self):

        self.anchored = False

        self.organisation = {
            'typeHash': str(self.typeHash),
            'inputsHash': str(self.inputsHash),
            'instanceHash': str(self.instanceHash),
            'hashID': self.hashID,
            'inputs': self.inputs,
            'meta': self.meta,
            'outs': {}
            }
        if not type(self) is Constructor:
            self.organisation['constructor'] = self.constructor

        self._add_weakref()

    def _add_weakref(self):
        self.ref = weakref.ref(self)
        BUILTS[self.hashID] = self.ref

    def __hash__(self):
        return self.instanceHash

    def _check_anchored(self):
        if not self.anchored:
            raise Exception(
                "Must be anchored first."
                )

    def anchor(self, frameID, path = ''):
        if mpi.rank == 0:
            os.makedirs(path, exist_ok = True)
        self.frameID = frameID
        self.path = path
        self.h5filename = os.path.join(os.path.abspath(path), frameID + '.frm')
        self._add_item(self.organisation, self.hashID)
        self.anchored = True
        if hasattr(self, 'count'):
            self._update_counts()
        self._post_anchor_hook()

    def _get_h5obj(self, names = []):
        # assumes h5file is open
        myobj = self.h5file
        for name in names:
            myobj = myobj[name]
        return myobj

    @disk.h5filewrap
    def _add_subgroup(self, name, groupNames = []):
        group = self._get_h5obj(groupNames)
        if group is None:
            group = self.h5file
        if name in group:
            subgroup = group[name]
        else:
            subgroup = group.create_group(name)
        return [*groupNames, name]

    @disk.h5filewrap
    def _add_attr(self, item, name, groupNames = []):
        group = self._get_h5obj(groupNames)
        group.attrs[name] = item

    @disk.h5filewrap
    def _add_ref(self, address, name, groupNames = []):
        group = self._get_h5obj(groupNames)
        ref = self.h5file[address].ref
        group.attrs[name] = ref

    @disk.h5filewrap
    def _add_dataset(self, data, key, groupNames = []):
        group = self.h5file[self.hashID]['/'.join(groupNames)]
        if key in group:
            dataset = group[key]
        else:
            maxshape = [None, *data.shape[1:]]
            dataset = group.create_dataset(
                name = key,
                shape = [0, *data.shape[1:]],
                maxshape = maxshape,
                dtype = data.dtype
                )
        priorlen = dataset.shape[0]
        dataset.resize(priorlen + len(data), axis = 0)
        dataset[priorlen:] = data

    @disk.h5filewrap
    def _add_link(self, item, name, groupNames = []):
        group = self._get_h5obj(groupNames)
        group[name] = self.h5file[item]

    @disk.h5filewrap
    def _check_item(self, name, groupNames = []):
        group = self._get_h5obj(groupNames)
        return name in group

    def _add_item(self, item, name, groupNames = []):
        if not self._check_item(name, groupNames):
            if type(item) is dict:
                subgroupNames = self._add_subgroup(name, groupNames)
                for subname, subitem in sorted(item.items()):
                    self._add_item(subitem, subname, subgroupNames)
            elif isinstance(item, Built):
                if not self._check_item(item.hashID):
                    item.anchor(self.frameID, self.path)
                # self._add_link(item.hashID, name, groupNames)
                self._add_ref(item.hashID, name, groupNames)
            else:
                self._add_attr(item, name, groupNames)

    def _coanchored(self, coBuilt):
        if hasattr(self, 'h5filename') and hasattr(coBuilt, 'h5filename'):
            return self.h5filename == coBuilt.h5filename
        else:
            return False

    def coanchor(self, coBuilt):
        if not coBuilt.anchored:
            raise Exception("Trying to coanchor to unanchored built!")
        if not self._coanchored(coBuilt):
            self.anchor(coBuilt.frameID, coBuilt.path)

    def _post_anchor_hook(self):
        pass

    def file(self):
        return h5py.File(self.h5filename)

from .constructor import Constructor
