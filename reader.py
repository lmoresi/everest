import h5py
from functools import partial
import os
import numpy as np

from . import disk
from . import utilities
from .fetch import Fetch
from .scope import Scope

class Reader:

    def __init__(
            self,
            name,
            outputPath
            ):
        self.h5file = None
        self.h5filename = os.path.join(os.path.abspath(outputPath), name + '.frm')
        self.file = partial(h5py.File, self.h5filename, 'r')

    @disk.h5filewrap
    def pull(self, scope, keys):
        if type(keys) is str:
            keys = (keys,)
        outs = []
        for key in keys:
            outs.append(self._pull(scope, key))
        if len(outs) == 1:
            return outs[0]
        else:
            return tuple(outs)

    def _pull(self, scope, key):
        arrList = []
        for superkey, scopeCounts in scope:
            thisGroup = self.h5file[superkey]
            thisTargetDataset = thisGroup['outs'][key]
            if scopeCounts == '...':
                arr = thisTargetDataset[...]
            else:
                thisCountsDataset = thisGroup['outs']['_counts_']
                maskArr = np.isin(
                    thisCountsDataset,
                    scopeCounts,
                    assume_unique = True
                    )
                slicer = (
                    maskArr,
                    *[slice(None) for i in range(1, len(thisTargetDataset.shape))]
                    )
                arr = thisTargetDataset[slicer]
            arrList.append(arr)
        try:
            allArr = np.concatenate(arrList)
            return allArr
        except ValueError:
            allTuple = tuple(arrList)
            return allTuple

    @classmethod
    def _seek(cls, key, searchArea):
        # expects h5filewrap
        splitkey = key.split('/')
        primekey = splitkey[0]
        remkey = '/'.join(splitkey[1:])
        if primekey == '**':
            found = cls._seek('*/' + remkey, searchArea)
            found[''] = cls._seek('*/' + key, searchArea)
        elif primekey == '*':
            localkeys = {*searchArea, *searchArea.attrs}
            searchkeys = [
                localkey + '/' + remkey \
                    for localkey in localkeys
                ]
            found = dict()
            for searchkey in searchkeys:
                try:
                    found[searchkey.split('/')[0]] = \
                        cls._seek(searchkey, searchArea)
                except:
                    pass
        else:
            try:
                found = searchArea[primekey]
            except:
                found = searchArea.attrs[primekey]
            if not remkey == '':
                found = cls._seek(remkey, found)
        return found

    def _seekresolve(self, toResolve):
        # expects h5filewrap
        if type(toResolve) is dict:
            out = dict()
            for key, val in toResolve.items():
                out[key] = self._seekresolve(val)
        elif type(toResolve) is h5py.Group:
            out = toResolve.name
        elif type(toResolve) is h5py.Dataset:
            out = np.array(toResolve)
        elif type(toResolve) is h5py.Reference:
            out = self.h5file[toResolve].attrs['hashID']
        elif isinstance(toResolve, np.generic):
            out = np.asscalar(toResolve)
        else:
            out = toResolve
        return out

    @staticmethod
    def _process_fetch(inFetch, context):
        inDict = inFetch(context)
        outs = set()
        for key, result in inDict.items():
            superkey = key.split('/')[0]
            indices = None
            try:
                if result:
                    indices = '...'
            except ValueError:
                if np.all(result):
                    indices = '...'
                elif np.any(result):
                    countsPath = '/' + '/'.join((
                        superkey,
                        'outs',
                        '_counts_'
                        ))
                    counts = context(countsPath)
                    indices = counts[result.flatten()]
                    indices = tuple(indices)
            except:
                raise TypeError
            if not indices is None:
                outs.add((superkey, indices))
        return outs

    def _gettuple(self, inp):
        return [self.__getitem__(subInp) for subInp in inp]

    @disk.h5filewrap
    def _getstr(self, key):
        if key == '':
            key = '**'
        elif key[0] == '/':
            key = key[1:]
        elif not key[:2] == '**':
            key = '**/' + key
        sought = self._seek(key, self.h5file)
        resolved = self._seekresolve(sought)
        if type(resolved) is dict:
            out = utilities.flatten(resolved, sep = '/')
        else:
            out = resolved
        return out

    def _getfetch(self, fetch):
        processed = self._process_fetch(fetch, self.__getitem__)
        sources = ('Scope', (fetch,))
        return Scope(processed, sources = sources)

    def _getslice(self, inp):
        if type(inp.start) is Scope:
            inScope = inp.start
        elif type(inp.start) is Fetch:
            inScope = self.__getitem__(inp.start)
        else:
            raise TypeError
        if not type(inp.stop) in {str, tuple}:
            raise TypeError
        return self.pull(inScope, inp.stop)

    def _getellipsis(self, inp):
        return self._getfetch(Fetch('/*'))

    _getmethods = {
        tuple: _gettuple,
        str: _getstr,
        Fetch: _getfetch,
        slice: _getslice,
        type(Ellipsis): _getellipsis
        }

    def __getitem__(self, inp):
        if type(inp) in self._getmethods:
            return self._getmethods[type(inp)](self, inp)
        else:
            if type(inp) is Scope:
                raise ValueError(
                    "Must provide a key to pull data from a scope"
                    )
            raise TypeError("Input not recognised: ", inp)

    context = __getitem__

    @disk.h5filewrap
    def get(self, *names):
        h5obj = self.h5file
        for name in names:
            if name == 'attrs':
                h5obj = h5obj.attrs
            else:
                h5obj = h5obj[name]
                if type(h5obj) is h5py.Reference:
                    h5obj = h5file[h5obj]
        h5obj = self._process_h5obj(h5obj, self.h5file, self.h5filename)
        return h5obj

    def _process_h5obj(self, h5obj, h5file, framePath):
        # expects filewrap
        if type(h5obj) is h5py.Group:
            return h5obj.name
        elif type(h5obj) is h5py.Dataset:
            return h5obj[...]
        elif type(h5obj) is h5py.AttributeManager:
            inDict, outDict = h5obj.items(), dict()
            for key, val in sorted(inDict):
                outDict[key] = self._process_h5obj(val, h5file, framePath)
            return outDict
        elif type(h5obj) is h5py.Reference:
            return '_path_' + os.path.join(framePath, h5file[h5obj].name)
        else:
            array = np.array(h5obj)
            try:
                return array.item()
            except ValueError:
                return list(array)
