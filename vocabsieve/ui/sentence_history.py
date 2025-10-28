from typing import Optional


class SentenceHistory:
    """Track in-memory history for the sentence text edit."""

    def __init__(self, initial: str = "", max_nodes: int = 100) -> None:
        self._max_nodes = max(2, max_nodes)
        start = initial or ""
        self._items: list[str] = [start]
        self._index: int = 0

    def checkpoint(self, text: str) -> None:
        value = text or ""
        if self._items[self._index] == value:
            return
        if self._index < len(self._items) - 1:
            self._items = self._items[: self._index + 1]
        self._items.append(value)
        self._index += 1
        self._trim()

    def replace_current(self, text: str) -> None:
        self._items[self._index] = text or ""

    def can_step(self, delta: int) -> bool:
        new_index = self._index + delta
        return 0 <= new_index < len(self._items)

    def step(self, delta: int) -> Optional[str]:
        if not self.can_step(delta):
            return None
        self._index += delta
        return self._items[self._index]

    def position(self) -> tuple[int, int]:
        return self._index + 1, len(self._items)

    def _trim(self) -> None:
        if len(self._items) <= self._max_nodes:
            return
        drop = len(self._items) - self._max_nodes
        self._items = self._items[drop:]
        self._index -= drop
        if self._index < 0:
            self._index = 0

    def __len__(self) -> int:
        return len(self._items)
