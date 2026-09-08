"""Where uploaded report files live.

Uploads are written through an interface rather than straight to disk. The
local implementation is the only one here and is what runs in development, but
nothing above this module knows that: the pipeline stores and reads a *key*, and
a deployment that needs durable object storage can add a second implementation
of ReportStorage without any change to the routes, the extraction step, or the
database records.

Two things are enforced here rather than trusted from the request:

The stored name is generated. An uploaded filename is attacker-controlled text
and is never used to build a path; the original is kept as a label only.

Files are separated by user. A key always begins with the owner's id, so a key
belonging to one user cannot resolve into another user's directory even if it
were somehow guessed.
"""

import os
import re
import shutil
from uuid import uuid4

from config import (
    REPORT_ALLOWED_EXTENSIONS,
    REPORT_MAX_UPLOAD_BYTES,
    REPORT_STORAGE_BACKEND,
    REPORT_STORAGE_DIR,
)

# A key is "<user_id>/<uuid><ext>". Nothing else is a valid key, which is what
# makes path traversal impossible rather than merely unlikely.
KEY_PATTERN = re.compile(r"^[0-9a-f]{24}/[0-9a-f]{32}\.[a-z0-9]{1,8}$")

USER_ID_PATTERN = re.compile(r"^[0-9a-f]{24}$")


class StorageError(RuntimeError):
    """Raised when a file cannot be stored or read."""


class UploadRejected(ValueError):
    """Raised when the uploaded file is not something we accept."""


def _extension(filename: str) -> str:
    extension = os.path.splitext(filename or "")[1].lower()

    if extension not in REPORT_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(REPORT_ALLOWED_EXTENSIONS))

        raise UploadRejected(
            f"{extension or 'That file type'} is not accepted. "
            f"Upload one of: {allowed}."
        )

    return extension


class StoredFile:
    """The result of storing one upload."""

    def __init__(self, key: str, size_bytes: int, extension: str):
        self.key = key
        self.size_bytes = size_bytes
        self.extension = extension

    def as_record(self) -> dict:
        return {
            "key": self.key,
            "size_bytes": self.size_bytes,
            "extension": self.extension,
        }


class ReportStorage:
    """The interface the rest of the pipeline depends on."""

    name = "abstract"

    def save(self, user_id: str, filename: str, stream) -> StoredFile:
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalReportStorage(ReportStorage):
    """Files on the machine running the API. Fine for development."""

    name = "local"

    def __init__(self, root: str = REPORT_STORAGE_DIR):
        self.root = os.path.abspath(root)

    def _path_for(self, key: str) -> str:
        if not KEY_PATTERN.match(key or ""):
            raise StorageError("That is not a valid stored file key")

        path = os.path.abspath(os.path.join(self.root, key))

        # Belt and braces: even with the pattern above, never return a path
        # that escapes the storage root.
        if not path.startswith(self.root + os.sep):
            raise StorageError("That is not a valid stored file key")

        return path

    def save(self, user_id: str, filename: str, stream) -> StoredFile:
        if not USER_ID_PATTERN.match(user_id or ""):
            raise StorageError("A stored file needs a valid owner id")

        extension = _extension(filename)

        key = f"{user_id}/{uuid4().hex}{extension}"
        path = self._path_for(key)

        os.makedirs(os.path.dirname(path), exist_ok=True)

        size = 0

        try:
            with open(path, "wb") as destination:
                while True:
                    chunk = stream.read(1024 * 256)

                    if not chunk:
                        break

                    size += len(chunk)

                    # Checked while writing, not from a client-supplied length,
                    # and the partial file is removed before raising.
                    if size > REPORT_MAX_UPLOAD_BYTES:
                        destination.close()
                        self.delete(key)

                        limit_mb = REPORT_MAX_UPLOAD_BYTES // (1024 * 1024)

                        raise UploadRejected(
                            f"That file is larger than the {limit_mb} MB limit."
                        )

                    destination.write(chunk)

        except UploadRejected:
            raise

        except OSError as error:
            raise StorageError(f"The file could not be saved: {error}") from error

        if size == 0:
            self.delete(key)

            raise UploadRejected("That file is empty.")

        return StoredFile(key=key, size_bytes=size, extension=extension)

    def read_bytes(self, key: str) -> bytes:
        path = self._path_for(key)

        try:
            with open(path, "rb") as source:
                return source.read()

        except FileNotFoundError:
            raise StorageError("The stored file is missing") from None

        except OSError as error:
            raise StorageError(f"The file could not be read: {error}") from error

    def delete(self, key: str) -> bool:
        try:
            path = self._path_for(key)

        except StorageError:
            return False

        try:
            os.remove(path)

            return True

        except FileNotFoundError:
            return False

        except OSError:
            return False

    def exists(self, key: str) -> bool:
        try:
            return os.path.isfile(self._path_for(key))

        except StorageError:
            return False


_BACKENDS = {
    "local": LocalReportStorage,
}

_storage = None


def get_storage() -> ReportStorage:
    """The configured storage, created once.

    Unknown values fail loudly instead of silently falling back to local disk:
    a deployment that meant to use object storage should not quietly start
    writing to a container filesystem that disappears on restart.
    """

    global _storage

    if _storage is None:
        backend = _BACKENDS.get(REPORT_STORAGE_BACKEND)

        if backend is None:
            raise StorageError(
                f"REPORT_STORAGE_BACKEND={REPORT_STORAGE_BACKEND!r} is not a "
                f"storage backend this build knows. "
                f"Available: {', '.join(sorted(_BACKENDS))}."
            )

        _storage = backend()

    return _storage


def cleanup_directory_if_empty(user_id: str) -> None:
    """Remove a user's upload directory once nothing is left in it."""

    storage = get_storage()

    if not isinstance(storage, LocalReportStorage):
        return

    directory = os.path.join(storage.root, user_id)

    try:
        if os.path.isdir(directory) and not os.listdir(directory):
            shutil.rmtree(directory)

    except OSError:
        pass
