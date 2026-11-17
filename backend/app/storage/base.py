"""Storage backend interface (P0: de-hardcode upload directory)."""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class StoredObject:
    key: str
    size: int
    sha256: str
    mime_type: str


class StorageBackend(abc.ABC):
    @abc.abstractmethod
    def save(self, key: str, data: bytes, mime_type: str) -> StoredObject: ...

    @abc.abstractmethod
    def read(self, key: str) -> bytes: ...

    @abc.abstractmethod
    def delete(self, key: str) -> None: ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool: ...

    @abc.abstractmethod
    def signed_url(self, key: str, expires_in: int, filename: str | None = None) -> str: ...
