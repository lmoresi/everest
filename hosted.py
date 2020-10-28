import weakref

class Hosted:

    def __init__(self, host):
        self._host = weakref.ref(host)
        super().__init__()

    @property
    def host(self):
        host = self._host()
        assert not host is None
        return host
