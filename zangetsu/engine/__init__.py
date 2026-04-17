"""Engine module — shared infrastructure consumed by all Arenas."""

def __getattr__(name):
    if name == "ArenaEngine":
        from .core import ArenaEngine
        return ArenaEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["ArenaEngine"]
