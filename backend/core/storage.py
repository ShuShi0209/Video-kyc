"""Local-filesystem media storage.

Callers work with *logical keys* such as ``recordings/<attempt_id>/recording.webm``. The physical
location (``settings.storage_root / key``) is never exposed through the API.
"""
import os
import uuid
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from .config import settings

CHUNK_SIZE = 1024 * 1024


class StorageError(Exception):
    """The file could not be stored."""


class StorageLimitExceeded(StorageError):
    """The stream was larger than the allowed maximum."""


class LocalStorageProvider:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise StorageError(f"Storage key escapes the storage root: {key!r}")
        return path

    def exists(self, key: str) -> bool:
        return self.resolve(key).is_file()

    def delete(self, key: str) -> None:
        self.resolve(key).unlink(missing_ok=True)

    def move(self, source_key: str, target_key: str) -> None:
        source, target = self.resolve(source_key), self.resolve(target_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)

    def save_stream(
        self,
        key: str,
        stream: BinaryIO,
        max_bytes: int,
        head_check: Optional[Callable[[bytes], None]] = None,
    ) -> int:
        """Write ``stream`` to ``key`` atomically and return the number of bytes stored.

        ``head_check`` receives the first chunk (``b""`` for an empty stream) and may raise to
        reject the upload. Nothing is left behind on failure: data goes to a temp file that is
        only renamed into place once the whole stream was accepted.
        """
        target = self.resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        size = 0
        checked = False
        try:
            with open(temp, "wb") as out:
                while True:
                    chunk = stream.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    if not checked:
                        if head_check:
                            head_check(chunk)
                        checked = True
                    size += len(chunk)
                    if size > max_bytes:
                        raise StorageLimitExceeded(f"Upload exceeds the {max_bytes} byte limit")
                    out.write(chunk)
            if not checked and head_check:
                head_check(b"")
            os.replace(temp, target)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
        return size


def get_storage() -> LocalStorageProvider:
    return LocalStorageProvider(settings.storage_root)
