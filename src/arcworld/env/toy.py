"""A tiny deterministic hidden-rule world for smoke tests and dashboard demos."""

from __future__ import annotations

from copy import deepcopy

from arcworld.types import Action, ActionKind, GameStatus, Observation, freeze_grid

TOY_MODEL_SOURCE = """
def initial_state(observation):
    grid = deepcopy(observation["frames"][-1])
    player = None
    key = None
    goal = None
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == 9:
                player = [x, y]
            elif cell == 11:
                key = [x, y]
            elif cell == 14:
                goal = [x, y]
    return {
        "grid": grid,
        "player": player,
        "key": key,
        "goal": goal,
        "has_key": False,
        "status": "NOT_FINISHED",
        "levels_completed": 0,
        "win_levels": 1,
    }

def step(state, action):
    state = deepcopy(state)
    directions = {
        1: [0, -1],
        2: [0, 1],
        3: [-1, 0],
        4: [1, 0],
    }
    if action["id"] not in directions or state["status"] != "NOT_FINISHED":
        return state
    dx, dy = directions[action["id"]]
    x, y = state["player"]
    nx, ny = x + dx, y + dy
    target = state["grid"][ny][nx]
    if target == 5:
        return state
    if target == 8 and not state["has_key"]:
        return state
    state["grid"][y][x] = 0
    if target == 11:
        state["has_key"] = True
        state["key"] = None
    state["player"] = [nx, ny]
    state["grid"][ny][nx] = 9
    if state["goal"] == [nx, ny]:
        state["status"] = "WIN"
        state["levels_completed"] = 1
    return state

def render(state):
    return state["grid"]

def status(state):
    return state["status"]

def metrics(state):
    return {
        "levels_completed": state["levels_completed"],
        "win_levels": state["win_levels"],
    }

def is_goal(state):
    return state["status"] == "WIN"
"""


class ToyKeyDoorEnvironment:
    """Move right, collect the key, unlock the door, and reach the goal."""

    def __init__(self) -> None:
        self._initial = _initial_grid()
        self._grid = deepcopy(self._initial)
        self._player = (1, 1)
        self._has_key = False
        self._status = GameStatus.NOT_FINISHED
        self._undo: list[tuple[list[list[int]], tuple[int, int], bool, GameStatus]] = []

    def reset(self) -> Observation:
        self._grid = deepcopy(self._initial)
        self._player = (1, 1)
        self._has_key = False
        self._status = GameStatus.NOT_FINISHED
        self._undo.clear()
        return self._observation(full_reset=True)

    def start(self) -> Observation:
        return self._observation(full_reset=True)

    def step(self, action: Action) -> Observation:
        if action.kind is ActionKind.RESET:
            return self.reset()
        if action.kind is ActionKind.ACTION7:
            if self._undo:
                self._grid, self._player, self._has_key, self._status = self._undo.pop()
            return self._observation()
        if self._status is not GameStatus.NOT_FINISHED:
            return self._observation()
        directions = {
            ActionKind.ACTION1: (0, -1),
            ActionKind.ACTION2: (0, 1),
            ActionKind.ACTION3: (-1, 0),
            ActionKind.ACTION4: (1, 0),
        }
        if action.kind not in directions:
            return self._observation()
        self._undo.append((deepcopy(self._grid), self._player, self._has_key, self._status))
        dx, dy = directions[action.kind]
        x, y = self._player
        nx, ny = x + dx, y + dy
        target = self._grid[ny][nx]
        if target == 5 or (target == 8 and not self._has_key):
            return self._observation()
        self._grid[y][x] = 0
        if target == 11:
            self._has_key = True
        self._player = nx, ny
        self._grid[ny][nx] = 9
        if (nx, ny) == (8, 1):
            self._status = GameStatus.WIN
        return self._observation()

    def _observation(self, *, full_reset: bool = False) -> Observation:
        return Observation(
            frames=(freeze_grid(self._grid),),
            status=self._status,
            available_actions=tuple(ActionKind(index) for index in (1, 2, 3, 4, 5, 7)),
            levels_completed=1 if self._status is GameStatus.WIN else 0,
            win_levels=1,
            full_reset=full_reset,
            game_id="synthetic-key-door",
        )


def _initial_grid() -> list[list[int]]:
    grid = [[5] * 12]
    grid.extend([[5] + [0] * 10 + [5] for _ in range(6)])
    grid.append([5] * 12)
    grid[1][1] = 9
    grid[1][3] = 11
    grid[1][5] = 8
    grid[1][8] = 14
    grid[3][2:10] = [5] * 8
    return grid
