"""OS-held single-writer locks; process death releases ownership."""
import os
from pathlib import Path

class StateLocks:
    def __init__(self, paths):
        self.paths = sorted({str(Path(path).resolve()) for path in paths})
        self.handles = []

    def acquire(self):
        try:
            for path in self.paths:
                lock = Path(path + ".lock")
                lock.parent.mkdir(parents=True, exist_ok=True)
                handle = lock.open("a+b")
                try:
                    if os.name == "nt":
                        import msvcrt
                        handle.seek(0)
                        if not handle.read(1):handle.write(b"0");handle.flush()
                        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                except OSError:
                    handle.close()
                    raise RuntimeError("state already owned by another coordinator or backup") from None
                self.handles.append(handle)
            return self
        except Exception:
            self.close();raise

    def close(self):
        for handle in reversed(self.handles):
            if os.name == "nt":
                import msvcrt
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
            handle.close()
        self.handles.clear()

    def __enter__(self):return self.acquire()
    def __exit__(self,*args):self.close()
