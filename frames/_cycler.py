from . import Frame

class Cycler(Frame):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    def __call__(self):
        self._cycle()
    def _cycle(self):
        pass
