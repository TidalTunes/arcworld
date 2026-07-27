"""Relations derived from geometry; all are observations, not causal claims."""

from __future__ import annotations

from arcworld.perception.schema import Relation, SceneObject


def infer_relations(objects: tuple[SceneObject, ...]) -> tuple[Relation, ...]:
    relations: list[Relation] = []
    for index, first in enumerate(objects):
        for second in objects[index + 1 :]:
            relations.extend(_pair_relations(first, second))
    return tuple(
        sorted(
            relations,
            key=lambda item: (item.subject, item.predicate, item.object),
        )
    )


def _pair_relations(first: SceneObject, second: SceneObject) -> list[Relation]:
    relations: list[Relation] = []
    first_x, first_y = first.centroid
    second_x, second_y = second.centroid

    if first.bbox.right < second.bbox.x:
        _opposites(relations, first, "left_of", second, "right_of")
    elif second.bbox.right < first.bbox.x:
        _opposites(relations, second, "left_of", first, "right_of")
    if first.bbox.bottom < second.bbox.y:
        _opposites(relations, first, "above", second, "below")
    elif second.bbox.bottom < first.bbox.y:
        _opposites(relations, second, "above", first, "below")

    if abs(first_x - second_x) < 0.5:
        _symmetric(relations, first, "aligned_x", second)
    if abs(first_y - second_y) < 0.5:
        _symmetric(relations, first, "aligned_y", second)
    if _touching(first, second):
        _symmetric(relations, first, "touching", second, evidence="4-neighbor pixels")
    if first.bbox.contains(second.bbox, margin=1):
        _opposites(relations, first, "contains", second, "inside")
    elif second.bbox.contains(first.bbox, margin=1):
        _opposites(relations, second, "contains", first, "inside")
    if first.color == second.color:
        _symmetric(relations, first, "same_color", second)
    if first.shape == second.shape:
        _symmetric(relations, first, "same_shape", second)
    return relations


def _touching(first: SceneObject, second: SceneObject) -> bool:
    second_pixels = set(second.pixels)
    return any(
        (x + dx, y + dy) in second_pixels
        for x, y in first.pixels
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    )


def _symmetric(
    target: list[Relation],
    first: SceneObject,
    predicate: str,
    second: SceneObject,
    *,
    evidence: str = "",
) -> None:
    target.append(Relation(first.id, predicate, second.id, evidence=evidence))
    target.append(Relation(second.id, predicate, first.id, evidence=evidence))


def _opposites(
    target: list[Relation],
    first: SceneObject,
    predicate: str,
    second: SceneObject,
    inverse: str,
) -> None:
    target.append(Relation(first.id, predicate, second.id))
    target.append(Relation(second.id, inverse, first.id))
