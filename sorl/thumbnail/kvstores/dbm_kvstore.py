import os
from sorl.thumbnail.kvstores.base import KVStoreBase
from sorl.thumbnail.conf import settings
try:
    import anydbm as dbm
except ImportError:
    # Python 3, hopefully
    import dbm

#
# OS filesystem locking primitives.  TODO: Test Windows versions
#
if os.name == 'nt':
    import msvcrt

    def lock(f, readonly):
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def unlock(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def lock(f, readonly):
        fcntl.lockf(f.fileno(), fcntl.LOCK_SH if readonly else fcntl.LOCK_EX)

    def unlock(f):
        fcntl.lockf(f.fileno(), fcntl.LOCK_UN)


#
# A context manager to access the key-value store in a concurrent-safe manner.
#
class DBMContext(object):
    __slots__ = ('filename', 'mode', 'readonly', 'lockfile', 'db')

    def __init__(self, filename, mode, readonly):
        self.filename = filename
        self.mode = mode
        self.readonly = readonly
        self.lockfile = open(filename + ".lock", 'w+b')

    def __enter__(self):
        lock(self.lockfile, self.readonly)
        self.db = dbm.open(self.filename, 'c', self.mode)
        return self.db

    def __exit__(self, exval, extype, tb):
        self.db.close()
        unlock(self.lockfile)
        self.lockfile.close()


#
# Please note that all the coding effort is devoted to provide correct
# semantics, not performance.  Therefore, use this store only in development
# environments.
#
class KVStore(KVStoreBase):
    def __init__(self, *args, **kwargs):
        super(KVStore, self).__init__(*args, **kwargs)
        self.filename = settings.THUMBNAIL_DBM_FILE
        self.mode = settings.THUMBNAIL_DBM_MODE

    def _cast_key(self, key):
        return key if isinstance(key, bytes) else key.encode('utf-8')

    def _get_raw(self, key):
        with DBMContext(self.filename, self.mode, True) as db:
            return db.get(self._cast_key(key))

    def _set_raw(self, key, value):
        with DBMContext(self.filename, self.mode, False) as db:
            db[self._cast_key(key)] = value

    def _delete_raw(self, *keys):
        with DBMContext(self.filename, self.mode, False) as db:
            for key in keys:
                k = self._cast_key(key)
                if k in db:
                    del db[k]

    def _find_keys_raw(self, prefix):
        with DBMContext(self.filename, self.mode, True) as db:
            p = self._cast_key(prefix)
            return [k.decode('utf-8') for k in db.keys() if k.startswith(p)]
