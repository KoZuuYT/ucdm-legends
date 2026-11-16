"""Object pooling genérico: reaproveita objetos em vez de alocar/desalocar
a cada frame (evita picos de GC em projéteis, alvos e textos flutuantes)."""
from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")


class Pool(Generic[T]):
    def __init__(self, factory: Callable[[], T], size: int, *, grow: bool = True) -> None:
        self._factory = factory
        self._free: list[T] = [factory() for _ in range(size)]
        self.active: list[T] = []
        self.grow = grow

    def spawn(self) -> T | None:
        if self._free:
            obj = self._free.pop()
        elif self.grow:
            obj = self._factory()
        else:
            return None
        self.active.append(obj)
        return obj

    def release(self, obj: T) -> None:
        self.active.remove(obj)
        self._free.append(obj)

    def release_where(self, dead: Callable[[T], bool]) -> None:
        """Remove em lote (O(n)) todos os objetos que satisfazem `dead`."""
        keep = []
        for o in self.active:
            (self._free if dead(o) else keep).append(o)
        self.active = keep

    def clear(self) -> None:
        self._free.extend(self.active)
        self.active = []

    def __iter__(self) -> Iterator[T]:
        return iter(self.active)

    def __len__(self) -> int:
        return len(self.active)
