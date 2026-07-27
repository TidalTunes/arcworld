"""Object-centric frame parsing and comparison."""

from arcworld.perception.components import parse_scene, parse_scene_candidates
from arcworld.perception.diff import compare_grids, compare_observations, compare_scenes
from arcworld.perception.schema import BoundingBox, Relation, SceneGraph, SceneObject

__all__ = [
    "BoundingBox",
    "Relation",
    "SceneGraph",
    "SceneObject",
    "compare_grids",
    "compare_observations",
    "compare_scenes",
    "parse_scene",
    "parse_scene_candidates",
]
