"""Event bus mínimo para desacoplar sistemas (ex.: combate -> áudio/partículas/UI)."""
from collections import defaultdict
from typing import Any, Callable

Handler = Callable[..., Any]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def on(self, event: str, handler: Handler) -> Callable[[], None]:
        self._handlers[event].append(handler)
        return lambda: self.off(event, handler)

    def off(self, event: str, handler: Handler) -> None:
        if handler in self._handlers.get(event, ()):
            self._handlers[event].remove(handler)

    def emit(self, event: str, **payload: Any) -> None:
        for h in list(self._handlers.get(event, ())):
            h(**payload)

    def clear(self) -> None:
        self._handlers.clear()
