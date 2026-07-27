"""Greedy, deterministic object identity tracking with explicit uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from arcworld.perception.relations import infer_relations
from arcworld.perception.schema import SceneGraph, SceneObject


@dataclass(frozen=True, slots=True)
class TrackEvent:
    kind: str
    before_id: str | None
    after_id: str | None
    cost: float


@dataclass(slots=True)
class ObjectTracker:
    max_cost: float = 8.0
    next_id: int = 0

    def initialize(self, scene: SceneGraph) -> tuple[SceneGraph, tuple[TrackEvent, ...]]:
        renamed: list[SceneObject] = []
        events: list[TrackEvent] = []
        for item in scene.objects:
            object_id = self._new_id()
            renamed.append(item.renamed(object_id))
            events.append(TrackEvent("created", None, object_id, 0.0))
        graph = _replace_scene(scene, tuple(renamed))
        return graph, tuple(events)

    def update(
        self, previous: SceneGraph, current: SceneGraph
    ) -> tuple[SceneGraph, tuple[TrackEvent, ...]]:
        candidates = sorted(
            (
                (_match_cost(before, after), before.id, index)
                for before in previous.objects
                for index, after in enumerate(current.objects)
            ),
            key=lambda item: (item[0], item[1], item[2]),
        )
        assigned_before: set[str] = set()
        assigned_after: set[int] = set()
        names: dict[int, str] = {}
        events: list[TrackEvent] = []
        for cost, before_id, after_index in candidates:
            if cost > self.max_cost:
                break
            if before_id in assigned_before or after_index in assigned_after:
                continue
            assigned_before.add(before_id)
            assigned_after.add(after_index)
            names[after_index] = before_id
            events.append(TrackEvent("matched", before_id, before_id, cost))

        for before in previous.objects:
            if before.id not in assigned_before:
                events.append(TrackEvent("removed", before.id, None, self.max_cost))
        for index in range(len(current.objects)):
            if index not in assigned_after:
                names[index] = self._new_id()
                events.append(TrackEvent("created", None, names[index], 0.0))

        objects = tuple(item.renamed(names[index]) for index, item in enumerate(current.objects))
        return _replace_scene(current, objects), tuple(events)

    def _new_id(self) -> str:
        object_id = f"t{self.next_id}"
        self.next_id += 1
        return object_id


def _match_cost(before: SceneObject, after: SceneObject) -> float:
    bx, by = before.centroid
    ax, ay = after.centroid
    distance = hypot(bx - ax, by - ay)
    color_penalty = 0.0 if before.color == after.color else 6.0
    shape_penalty = 0.0 if before.shape == after.shape else 2.0
    area_penalty = abs(before.area - after.area) / max(before.area, after.area)
    return distance + color_penalty + shape_penalty + area_penalty


def _replace_scene(scene: SceneGraph, objects: tuple[SceneObject, ...]) -> SceneGraph:
    return SceneGraph(
        width=scene.width,
        height=scene.height,
        background=scene.background,
        objects=objects,
        relations=infer_relations(objects),
        ontology=scene.ontology,
        confidence=scene.confidence,
    )
