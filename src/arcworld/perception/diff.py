"""Exact and semantic comparison primitives."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from arcworld.perception.components import parse_scene
from arcworld.perception.schema import BoundingBox, SceneGraph, SceneObject
from arcworld.types import Grid, Observation


@dataclass(frozen=True, slots=True)
class PixelDiff:
    equal: bool
    changed: int
    total: int
    ratio: float
    regions: tuple[BoundingBox, ...]
    changed_pixels: tuple[tuple[int, int, int, int], ...]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "equal": self.equal,
            "changed": self.changed,
            "total": self.total,
            "ratio": self.ratio,
            "regions": [region.to_jsonable() for region in self.regions],
            "changed_pixels": [list(item) for item in self.changed_pixels],
        }


@dataclass(frozen=True, slots=True)
class ObjectDelta:
    kind: str
    before_id: str | None
    after_id: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class SceneDiff:
    deltas: tuple[ObjectDelta, ...]
    relation_added: tuple[tuple[str, str, str], ...]
    relation_removed: tuple[tuple[str, str, str], ...]

    @property
    def equal(self) -> bool:
        return not self.deltas and not self.relation_added and not self.relation_removed

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "equal": self.equal,
            "deltas": [
                {
                    "kind": item.kind,
                    "before_id": item.before_id,
                    "after_id": item.after_id,
                    "detail": item.detail,
                }
                for item in self.deltas
            ],
            "relation_added": [list(item) for item in self.relation_added],
            "relation_removed": [list(item) for item in self.relation_removed],
        }


@dataclass(frozen=True, slots=True)
class ObservationDiff:
    exact: bool
    pixels: PixelDiff
    scene: SceneDiff
    status_match: bool
    level_match: bool
    available_actions_match: bool
    full_reset_match: bool
    animation_frame_count_match: bool
    animation_frames_match: bool

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "exact": self.exact,
            "pixels": self.pixels.to_jsonable(),
            "scene": self.scene.to_jsonable(),
            "status_match": self.status_match,
            "level_match": self.level_match,
            "available_actions_match": self.available_actions_match,
            "full_reset_match": self.full_reset_match,
            "animation_frame_count_match": self.animation_frame_count_match,
            "animation_frames_match": self.animation_frames_match,
        }


def compare_grids(expected: Grid, actual: Grid) -> PixelDiff:
    if (len(expected), len(expected[0])) != (len(actual), len(actual[0])):
        raise ValueError("cannot compare grids with different shapes")
    changed = tuple(
        (x, y, expected[y][x], actual[y][x])
        for y in range(len(expected))
        for x in range(len(expected[0]))
        if expected[y][x] != actual[y][x]
    )
    total = len(expected) * len(expected[0])
    return PixelDiff(
        equal=not changed,
        changed=len(changed),
        total=total,
        ratio=len(changed) / total,
        regions=_changed_regions({(x, y) for x, y, _, _ in changed}),
        changed_pixels=changed,
    )


def compare_scenes(expected: SceneGraph, actual: SceneGraph) -> SceneDiff:
    unmatched_actual = list(actual.objects)
    deltas: list[ObjectDelta] = []
    mapping: dict[str, str] = {}
    for before in expected.objects:
        if not unmatched_actual:
            deltas.append(ObjectDelta("removed", before.id, None, _summary(before)))
            continue
        after = min(unmatched_actual, key=lambda item: _object_distance(before, item))
        distance = _object_distance(before, after)
        if distance > 10:
            deltas.append(ObjectDelta("removed", before.id, None, _summary(before)))
            continue
        unmatched_actual.remove(after)
        mapping[before.id] = after.id
        if before.color != after.color:
            deltas.append(
                ObjectDelta("recolored", before.id, after.id, f"{before.color}->{after.color}")
            )
        if before.shape != after.shape:
            deltas.append(
                ObjectDelta("reshaped", before.id, after.id, f"area {before.area}->{after.area}")
            )
        if before.bbox != after.bbox:
            dx = after.bbox.x - before.bbox.x
            dy = after.bbox.y - before.bbox.y
            deltas.append(ObjectDelta("moved", before.id, after.id, f"delta=({dx},{dy})"))
    for after in unmatched_actual:
        deltas.append(ObjectDelta("created", None, after.id, _summary(after)))

    expected_relations = {
        (
            mapping.get(item.subject, item.subject),
            item.predicate,
            mapping.get(item.object, item.object),
        )
        for item in expected.relations
        if item.subject in mapping and item.object in mapping
    }
    actual_relations = {
        (item.subject, item.predicate, item.object)
        for item in actual.relations
        if item.subject in mapping.values() and item.object in mapping.values()
    }
    return SceneDiff(
        deltas=tuple(deltas),
        relation_added=tuple(sorted(actual_relations - expected_relations)),
        relation_removed=tuple(sorted(expected_relations - actual_relations)),
    )


def compare_observations(expected: Observation, actual: Observation) -> ObservationDiff:
    pixels = compare_grids(expected.latest, actual.latest)
    scene = compare_scenes(parse_scene(expected.latest), parse_scene(actual.latest))
    status_match = expected.status == actual.status
    level_match = (
        expected.levels_completed == actual.levels_completed
        and expected.win_levels == actual.win_levels
    )
    available_actions_match = expected.available_actions == actual.available_actions
    full_reset_match = expected.full_reset == actual.full_reset
    frame_count_match = len(expected.frames) == len(actual.frames)
    frames_match = frame_count_match and all(
        expected_frame == actual_frame
        for expected_frame, actual_frame in zip(expected.frames, actual.frames, strict=True)
    )
    return ObservationDiff(
        exact=(
            frames_match
            and status_match
            and level_match
            and available_actions_match
            and full_reset_match
        ),
        pixels=pixels,
        scene=scene,
        status_match=status_match,
        level_match=level_match,
        available_actions_match=available_actions_match,
        full_reset_match=full_reset_match,
        animation_frame_count_match=frame_count_match,
        animation_frames_match=frames_match,
    )


def _changed_regions(points: set[tuple[int, int]]) -> tuple[BoundingBox, ...]:
    regions: list[BoundingBox] = []
    while points:
        seed = points.pop()
        queue = deque([seed])
        component = {seed}
        while queue:
            x, y = queue.popleft()
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in points:
                    points.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        xs = [point[0] for point in component]
        ys = [point[1] for point in component]
        regions.append(BoundingBox(min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    return tuple(sorted(regions, key=lambda item: (item.y, item.x)))


def _object_distance(first: SceneObject, second: SceneObject) -> float:
    fx, fy = first.centroid
    sx, sy = second.centroid
    return (
        abs(fx - sx)
        + abs(fy - sy)
        + (0 if first.color == second.color else 4)
        + abs(first.area - second.area) / max(first.area, second.area)
    )


def _summary(item: SceneObject) -> str:
    return f"color={item.color}, area={item.area}, bbox={item.bbox.to_jsonable()}"
