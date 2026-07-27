"""Small, dependency-light types shared across the suite."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any, cast

Grid = tuple[tuple[int, ...], ...]


def freeze_grid(values: Iterable[Iterable[int]]) -> Grid:
    """Convert an array-like grid into an immutable, validated representation."""
    grid = tuple(tuple(int(cell) for cell in row) for row in values)
    if not grid or not grid[0]:
        raise ValueError("a grid must be non-empty")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid rows must have equal width")
    if any(cell < 0 or cell > 15 for row in grid for cell in row):
        raise ValueError("grid colors must be in the inclusive range 0..15")
    return grid


class GameStatus(StrEnum):
    NOT_PLAYED = "NOT_PLAYED"
    NOT_FINISHED = "NOT_FINISHED"
    WIN = "WIN"
    GAME_OVER = "GAME_OVER"


class ActionKind(IntEnum):
    RESET = 0
    ACTION1 = 1
    ACTION2 = 2
    ACTION3 = 3
    ACTION4 = 4
    ACTION5 = 5
    ACTION6 = 6
    ACTION7 = 7


@dataclass(frozen=True, slots=True)
class Action:
    """One environment action; ACTION6 is the only coordinate action."""

    kind: ActionKind
    x: int | None = None
    y: int | None = None

    def __post_init__(self) -> None:
        if self.kind is ActionKind.ACTION6:
            if self.x is None or self.y is None:
                raise ValueError("ACTION6 requires x and y")
            if not (0 <= self.x <= 63 and 0 <= self.y <= 63):
                raise ValueError("ACTION6 coordinates must be in 0..63")
        elif self.x is not None or self.y is not None:
            raise ValueError(f"{self.kind.name} does not accept coordinates")

    def to_jsonable(self) -> dict[str, int]:
        value = {"id": int(self.kind)}
        if self.kind is ActionKind.ACTION6:
            assert self.x is not None and self.y is not None
            value.update(x=self.x, y=self.y)
        return value

    @classmethod
    def from_jsonable(cls, value: Mapping[str, Any]) -> Action:
        return cls(
            kind=ActionKind(int(value["id"])),
            x=_optional_int(value.get("x")),
            y=_optional_int(value.get("y")),
        )

    @classmethod
    def named(cls, name: str, *, x: int | None = None, y: int | None = None) -> Action:
        return cls(ActionKind[name.upper()], x=x, y=y)

    def __str__(self) -> str:
        if self.kind is ActionKind.ACTION6:
            return f"{self.kind.name}({self.x},{self.y})"
        return self.kind.name


@dataclass(frozen=True, slots=True)
class Observation:
    """All frames and metadata returned by one environment operation."""

    frames: tuple[Grid, ...]
    status: GameStatus = GameStatus.NOT_FINISHED
    available_actions: tuple[ActionKind, ...] = ()
    levels_completed: int = 0
    win_levels: int = 0
    full_reset: bool = False
    game_id: str | None = None
    guid: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("an observation must contain at least one frame")

    @property
    def latest(self) -> Grid:
        return self.frames[-1]

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.latest), len(self.latest[0])

    def to_jsonable(self, *, expose_identity: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "frames": [[list(row) for row in grid] for grid in self.frames],
            "status": self.status.value,
            "available_actions": [int(action) for action in self.available_actions],
            "levels_completed": self.levels_completed,
            "win_levels": self.win_levels,
            "full_reset": self.full_reset,
            "metadata": dict(self.metadata),
        }
        if expose_identity:
            value.update(game_id=self.game_id, guid=self.guid)
        return value

    @classmethod
    def from_jsonable(cls, value: Mapping[str, Any]) -> Observation:
        raw_frames = value.get("frames", value.get("frame"))
        if raw_frames is None:
            raise ValueError("observation requires frames")
        return cls(
            frames=tuple(freeze_grid(_rows(frame)) for frame in raw_frames),
            status=_coerce_status(value.get("status", value.get("state", "NOT_FINISHED"))),
            available_actions=tuple(
                ActionKind(int(action)) for action in value.get("available_actions", ())
            ),
            levels_completed=int(value.get("levels_completed", 0)),
            win_levels=int(value.get("win_levels", 0)),
            full_reset=bool(value.get("full_reset", False)),
            game_id=_optional_str(value.get("game_id")),
            guid=_optional_str(value.get("guid")),
            metadata=dict(value.get("metadata", {})),
        )

    @classmethod
    def from_sdk(cls, raw: Any) -> Observation:
        """Convert an official FrameData/FrameDataRaw-like object without importing the SDK."""
        frames = getattr(raw, "frame", None)
        if not frames:
            raise ValueError("SDK response is empty")
        return cls(
            frames=tuple(freeze_grid(_rows(frame)) for frame in frames),
            status=_coerce_status(getattr(raw, "state", "NOT_FINISHED")),
            available_actions=tuple(
                ActionKind(int(action)) for action in getattr(raw, "available_actions", ())
            ),
            levels_completed=int(getattr(raw, "levels_completed", 0)),
            win_levels=int(getattr(raw, "win_levels", 0)),
            full_reset=bool(getattr(raw, "full_reset", False)),
            game_id=_optional_str(getattr(raw, "game_id", None)),
            guid=_optional_str(getattr(raw, "guid", None)),
        )


@dataclass(frozen=True, slots=True)
class Transition:
    """One immutable item in the evidence timeline."""

    index: int
    before: Observation
    action: Action
    after: Observation
    reasoning: Mapping[str, Any] = field(default_factory=dict)

    def to_jsonable(self, *, expose_identity: bool = True) -> dict[str, Any]:
        return {
            "index": self.index,
            "before": self.before.to_jsonable(expose_identity=expose_identity),
            "action": self.action.to_jsonable(),
            "after": self.after.to_jsonable(expose_identity=expose_identity),
            "reasoning": dict(self.reasoning),
        }

    @classmethod
    def from_jsonable(cls, value: Mapping[str, Any]) -> Transition:
        return cls(
            index=int(value["index"]),
            before=Observation.from_jsonable(_mapping(value["before"])),
            action=Action.from_jsonable(_mapping(value["action"])),
            after=Observation.from_jsonable(_mapping(value["after"])),
            reasoning=dict(_mapping(value.get("reasoning", {}))),
        )


def _rows(value: Any) -> Iterable[Iterable[int]]:
    if hasattr(value, "tolist"):
        return cast(Iterable[Iterable[int]], value.tolist())
    return cast(Iterable[Iterable[int]], value)


def _coerce_status(value: Any) -> GameStatus:
    raw = getattr(value, "value", value)
    return GameStatus(str(raw))


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"expected a mapping, got {type(value).__name__}")
    return value


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
