"""Serializable scene-graph primitives."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1

    @property
    def center(self) -> tuple[float, float]:
        return self.x + (self.width - 1) / 2, self.y + (self.height - 1) / 2

    def contains(self, other: BoundingBox, *, margin: int = 0) -> bool:
        return (
            self.x + margin <= other.x
            and self.y + margin <= other.y
            and self.right - margin >= other.right
            and self.bottom - margin >= other.bottom
        )

    def intersects(self, other: BoundingBox) -> bool:
        return not (
            self.right < other.x
            or other.right < self.x
            or self.bottom < other.y
            or other.bottom < self.y
        )

    def to_jsonable(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass(frozen=True, slots=True)
class SceneObject:
    id: str
    color: int
    pixels: tuple[tuple[int, int], ...]
    bbox: BoundingBox
    area: int
    perimeter: int
    holes: int
    shape: tuple[tuple[int, int], ...]
    attributes: Mapping[str, Any] = field(default_factory=dict)

    @property
    def centroid(self) -> tuple[float, float]:
        x = sum(pixel[0] for pixel in self.pixels) / self.area
        y = sum(pixel[1] for pixel in self.pixels) / self.area
        return x, y

    def renamed(self, object_id: str) -> SceneObject:
        return replace(self, id=object_id)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "color": self.color,
            "pixels": [list(pixel) for pixel in self.pixels],
            "bbox": self.bbox.to_jsonable(),
            "area": self.area,
            "perimeter": self.perimeter,
            "holes": self.holes,
            "shape": [list(pixel) for pixel in self.shape],
            "centroid": list(self.centroid),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True, slots=True)
class Relation:
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    evidence: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class SceneGraph:
    width: int
    height: int
    background: int
    objects: tuple[SceneObject, ...]
    relations: tuple[Relation, ...]
    ontology: str = "monochrome-components-4"
    confidence: float = 1.0

    def object_by_id(self, object_id: str) -> SceneObject:
        for item in self.objects:
            if item.id == object_id:
                return item
        raise KeyError(object_id)

    def with_objects(self, objects: tuple[SceneObject, ...]) -> SceneGraph:
        valid_ids = {item.id for item in objects}
        relations = tuple(
            relation
            for relation in self.relations
            if relation.subject in valid_ids and relation.object in valid_ids
        )
        return replace(self, objects=objects, relations=relations)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "background": self.background,
            "ontology": self.ontology,
            "confidence": self.confidence,
            "objects": [item.to_jsonable() for item in self.objects],
            "relations": [item.to_jsonable() for item in self.relations],
        }
