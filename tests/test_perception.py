from __future__ import annotations

from arcworld.perception.components import parse_scene, parse_scene_candidates
from arcworld.perception.diff import compare_grids, compare_observations, compare_scenes
from arcworld.perception.tracking import ObjectTracker
from arcworld.types import Observation, freeze_grid


def test_component_shape_holes_and_relations() -> None:
    grid = freeze_grid(
        [
            [0, 0, 0, 0, 0, 0],
            [0, 2, 2, 2, 2, 0],
            [0, 2, 0, 3, 2, 0],
            [0, 2, 0, 0, 2, 0],
            [0, 2, 2, 2, 2, 0],
            [0, 0, 0, 0, 0, 0],
        ]
    )
    scene = parse_scene(grid)
    ring = next(item for item in scene.objects if item.color == 2)
    inner = next(item for item in scene.objects if item.color == 3)
    assert ring.holes == 1
    assert ring.area == 12
    assert any(
        relation.subject == ring.id
        and relation.predicate == "contains"
        and relation.object == inner.id
        for relation in scene.relations
    )


def test_connectivity_alternatives_are_retained() -> None:
    grid = freeze_grid([[1, 0], [0, 1]])
    candidates = parse_scene_candidates(grid)
    counts = {
        candidate.ontology.split(":", maxsplit=1)[0]: len(candidate.objects)
        for candidate in candidates
        if candidate.background == 0
    }
    assert counts["monochrome-components-4"] == 2
    assert counts["monochrome-components-8"] == 1


def test_tracker_preserves_identity_across_motion() -> None:
    before = parse_scene(freeze_grid([[0, 0, 0], [0, 9, 0], [0, 0, 0]]))
    after = parse_scene(freeze_grid([[0, 0, 0], [0, 0, 9], [0, 0, 0]]))
    tracker = ObjectTracker()
    tracked_before, _ = tracker.initialize(before)
    tracked_after, events = tracker.update(tracked_before, after)
    assert tracked_before.objects[0].id == tracked_after.objects[0].id
    assert any(event.kind == "matched" for event in events)


def test_pixel_and_scene_diff_localize_change() -> None:
    before_grid = freeze_grid([[0, 0, 0], [0, 9, 0], [0, 0, 0]])
    after_grid = freeze_grid([[0, 0, 0], [0, 0, 9], [0, 0, 0]])
    pixels = compare_grids(before_grid, after_grid)
    assert pixels.changed == 2
    assert len(pixels.regions) == 1
    scene = compare_scenes(parse_scene(before_grid), parse_scene(after_grid))
    assert any(delta.kind == "moved" for delta in scene.deltas)


def test_observation_exactness_checks_intermediate_animation_pixels() -> None:
    final = freeze_grid([[0, 1]])
    predicted = Observation(frames=(freeze_grid([[1, 0]]), final))
    actual = Observation(frames=(freeze_grid([[0, 0]]), final))
    diff = compare_observations(predicted, actual)
    assert diff.pixels.equal
    assert diff.animation_frame_count_match
    assert not diff.animation_frames_match
    assert not diff.exact
