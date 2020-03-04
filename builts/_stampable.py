import ast

from .. import disk
from ._producer import Producer
from ._inquirer import Inquirer

class Stampable(Producer):

    def __init__(
        self,
        **kwargs
        ):

        self.stamps = [(self.hashID, 0),]

        super().__init__(**kwargs)

        # Producer attributes:
        self._post_save_fns.append(self._stampable_update)

        # Built attributes:
        self._post_anchor_fns.append(self._stampable_update)

    def stamp(self, stamper):
        if not isinstance(stamper, Inquirer):
            raise TypeError("Input must be Inquirer class.")
        self.stamps.append((stamper.hashID, self.count()))
        self.stamps = sorted(set(self.stamps))

    def _stampable_update(self):
        try:
            loaded = self.reader(self.hashID, 'stamps')
        except KeyError:
            loaded = []
        self.stamps = sorted(set([*self.stamps, *loaded]))
        self.writer.add(self.stamps, 'stamps', self.hashID)