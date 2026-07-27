"""Deterministic component extraction with explicit ontology alternatives."""

from __future__ import annotations

from collections import Counter, deque
from collections.abc import Iterable

from arcworld.perception.relations import infer_relations
from arcworld.perception.schema import BoundingBox, SceneGraph, SceneObject
from arcworld.types import Grid

_NEIGHBORS_4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
_NEIGHBORS_8 = _NEIGHBORS_4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def background_candidates(grid: Grid, limit: int = 3) -> tuple[tuple[int, float], ...]:
    """Rank background hypotheses using border support and global frequency."""
    height, width = len(grid), len(grid[0])
    border = (
        list(grid[0])
        + list(grid[-1])
        + [grid[y][0] for y in range(1, height - 1)]
        + [grid[y][-1] for y in range(1, height - 1)]
    )
    all_counts = Counter(cell for row in grid for cell in row)
    border_counts = Counter(border)
    total = height * width
    border_total = max(1, len(border))
    scores = {
        color: 0.7 * border_counts[color] / border_total + 0.3 * all_counts[color] / total
        for color in all_counts
    }
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return tuple(ranked[:limit])


def parse_scene(
    grid: Grid,
    *,
    background: int | None = None,
    connectivity: int = 4,
    ontology: str | None = None,
) -> SceneGraph:
    """Parse each same-color connected component as an object."""
    if connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8")
    if background is None:
        background = background_candidates(grid, limit=1)[0][0]
    height, width = len(grid), len(grid[0])
    neighbors = _NEIGHBORS_4 if connectivity == 4 else _NEIGHBORS_8
    unseen = {(x, y) for y in range(height) for x in range(width) if grid[y][x] != background}
    objects: list[SceneObject] = []

    while unseen:
        seed = min(unseen, key=lambda point: (point[1], point[0]))
        color = grid[seed[1]][seed[0]]
        component = _flood(seed, color, grid, unseen, neighbors)
        objects.append(_make_object(f"o{len(objects)}", color, component))

    objects.sort(key=lambda item: (item.bbox.y, item.bbox.x, item.color, -item.area))
    objects = [item.renamed(f"o{index}") for index, item in enumerate(objects)]
    relations = infer_relations(tuple(objects))
    return SceneGraph(
        width=width,
        height=height,
        background=background,
        objects=tuple(objects),
        relations=relations,
        ontology=ontology or f"monochrome-components-{connectivity}:background={background}",
    )


def parse_scene_candidates(grid: Grid, limit: int = 4) -> tuple[SceneGraph, ...]:
    """Retain plausible background/connectivity choices instead of collapsing early."""
    candidates: list[SceneGraph] = []
    ranked_backgrounds = background_candidates(grid, limit=2)
    for background, background_confidence in ranked_backgrounds:
        for connectivity in (4, 8):
            graph = parse_scene(grid, background=background, connectivity=connectivity)
            connectivity_prior = 1.0 if connectivity == 4 else 0.8
            candidates.append(
                SceneGraph(
                    width=graph.width,
                    height=graph.height,
                    background=graph.background,
                    objects=graph.objects,
                    relations=graph.relations,
                    ontology=graph.ontology,
                    confidence=background_confidence * connectivity_prior,
                )
            )
    candidates.sort(key=lambda graph: -graph.confidence)
    return tuple(candidates[:limit])


def _flood(
    seed: tuple[int, int],
    color: int,
    grid: Grid,
    unseen: set[tuple[int, int]],
    neighbors: Iterable[tuple[int, int]],
) -> set[tuple[int, int]]:
    height, width = len(grid), len(grid[0])
    queue = deque([seed])
    unseen.remove(seed)
    component = {seed}
    while queue:
        x, y = queue.popleft()
        for dx, dy in neighbors:
            point = x + dx, y + dy
            px, py = point
            if 0 <= px < width and 0 <= py < height and point in unseen and grid[py][px] == color:
                unseen.remove(point)
                component.add(point)
                queue.append(point)
    return component


def _make_object(object_id: str, color: int, pixels: set[tuple[int, int]]) -> SceneObject:
    xs = [point[0] for point in pixels]
    ys = [point[1] for point in pixels]
    left, top = min(xs), min(ys)
    bbox = BoundingBox(left, top, max(xs) - left + 1, max(ys) - top + 1)
    shape = tuple(sorted((x - left, y - top) for x, y in pixels))
    perimeter = sum((x + dx, y + dy) not in pixels for x, y in pixels for dx, dy in _NEIGHBORS_4)
    return SceneObject(
        id=object_id,
        color=color,
        pixels=tuple(sorted(pixels, key=lambda point: (point[1], point[0]))),
        bbox=bbox,
        area=len(pixels),
        perimeter=perimeter,
        holes=_count_holes(shape, bbox.width, bbox.height),
        shape=shape,
    )


def _count_holes(shape: tuple[tuple[int, int], ...], width: int, height: int) -> int:
    occupied = set(shape)
    empty = {(x, y) for y in range(height) for x in range(width)} - occupied
    holes = 0
    while empty:
        seed = next(iter(empty))
        queue = deque([seed])
        empty.remove(seed)
        touches_edge = seed[0] in (0, width - 1) or seed[1] in (0, height - 1)
        while queue:
            x, y = queue.popleft()
            for dx, dy in _NEIGHBORS_4:
                point = x + dx, y + dy
                if point in empty:
                    empty.remove(point)
                    queue.append(point)
                    touches_edge |= point[0] in (0, width - 1) or point[1] in (0, height - 1)
        if not touches_edge:
            holes += 1
    return holes
