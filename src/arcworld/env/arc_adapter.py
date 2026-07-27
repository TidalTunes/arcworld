"""Narrow adapter from a local ARC SDK wrapper to ARCWorld domain types.

The module has no import-time dependency on ``arc_agi`` or ``arcengine``.  It
can wrap an already-created environment (including a test double), or create an
official SDK environment in explicitly offline mode from previously downloaded
game files.  It intentionally contains no API-key, base-URL, normal-mode, or
online-mode setup.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, Self

from arcworld.types import Action, ActionKind, Observation

ActionEncoder = Callable[[Action], Any]


class EnvironmentWrapperLike(Protocol):
    """The small portion of the official wrapper API used by ARCWorld."""

    @property
    def observation_space(self) -> Any:
        """Return the most recent raw SDK observation."""

    def reset(self) -> Any | None:
        """Reset according to the environment's current reset semantics."""

    def step(
        self,
        action: Any,
        data: dict[str, int] | None = None,
        reasoning: dict[str, Any] | None = None,
    ) -> Any | None:
        """Apply one official SDK action."""


class ArcAdapterError(RuntimeError):
    """Base error for adapter or optional-SDK failures."""


class ActionUnavailableError(ArcAdapterError):
    """Raised before spending an action the current frame does not advertise."""


class EmptyObservationError(ArcAdapterError):
    """Raised when a wrapper operation returns no frame data."""


class ArcAdapter:
    """Translate between an ARC environment wrapper and ARCWorld values.

    ``available_actions`` is read from every current observation.  No metadata
    tag or action space captured at construction time is treated as authority.
    RESET is the one exception: the engine treats it as a control operation and
    current public games do not normally advertise action ID 0 in
    ``available_actions``.
    """

    def __init__(
        self,
        wrapper: EnvironmentWrapperLike,
        *,
        action_encoder: ActionEncoder | None = None,
        _sdk_owner: Any | None = None,
    ) -> None:
        self._wrapper = wrapper
        self._action_encoder = action_encoder or _encode_official_action
        # Retain an Arcade created by open_offline for the wrapper's lifetime.
        self._sdk_owner = _sdk_owner
        self._latest: Observation | None = None

    @classmethod
    def open_offline(
        cls,
        game_id: str,
        *,
        environments_dir: str | Path = "environment_files",
        recordings_dir: str | Path = "recordings",
        seed: int = 0,
        save_recording: bool = False,
        include_frame_data: bool = True,
        render_mode: str | None = None,
        renderer: Callable[[int, Any], None] | None = None,
    ) -> Self:
        """Open a previously downloaded game through SDK ``OFFLINE`` mode.

        The optional ``arc`` dependency must be installed and the directory
        must already contain the game's ``metadata.json`` and source file.
        This method never falls back to downloading a missing game.

        Version 0.9.9 lets ``OPERATION_MODE=competition`` override even an
        explicit constructor argument.  Refusing that environment value before
        constructing ``Arcade`` prevents an accidental remote session.
        """

        try:
            sdk = import_module("arc_agi")
        except ModuleNotFoundError as exc:
            raise ArcAdapterError(
                "offline ARC support is not installed; install the project 'arc' extra"
            ) from exc

        if os.getenv("OPERATION_MODE", "").strip().lower() == "competition":
            raise ArcAdapterError(
                "refusing to open a local environment while "
                "OPERATION_MODE=competition overrides SDK OFFLINE mode"
            )

        arcade = sdk.Arcade(
            arc_api_key="offline-local-only",
            operation_mode=sdk.OperationMode.OFFLINE,
            environments_dir=str(environments_dir),
            recordings_dir=str(recordings_dir),
        )
        resolved_mode = getattr(arcade.operation_mode, "value", arcade.operation_mode)
        if resolved_mode != "offline":
            raise ArcAdapterError(
                f"SDK resolved operation mode to {resolved_mode!r}, not 'offline'"
            )

        wrapper = arcade.make(
            game_id,
            seed=seed,
            save_recording=save_recording,
            include_frame_data=include_frame_data,
            render_mode=render_mode,
            renderer=renderer,
        )
        if wrapper is None:
            raise ArcAdapterError(f"game {game_id!r} was not found under {str(environments_dir)!r}")
        return cls(wrapper, _sdk_owner=arcade)

    @property
    def raw_wrapper(self) -> EnvironmentWrapperLike:
        """The injected SDK wrapper, for diagnostics outside model context."""

        return self._wrapper

    @property
    def observation(self) -> Observation:
        """Convert the wrapper's current observation without taking an action."""

        raw = self._wrapper.observation_space
        if raw is None:
            if self._latest is not None:
                return self._latest
            raise EmptyObservationError("environment has no current observation")
        self._latest = _convert_observation(raw)
        return self._latest

    @property
    def available_actions(self) -> tuple[ActionKind, ...]:
        """Actions advertised by the current frame, in environment order."""

        return self.observation.available_actions

    def start(self) -> Observation:
        """Return the observation created by ``Arcade.make`` without another reset."""

        return self.observation

    def accepts(self, action: Action) -> bool:
        """Whether the current observation permits an action.

        RESET remains available as an engine control operation even when it is
        absent from the advertised game actions.
        """

        return action.kind is ActionKind.RESET or action.kind in self.observation.available_actions

    def reset(self) -> Observation:
        """Request an SDK reset and return its complete frame sequence."""

        return self._remember(self._wrapper.reset(), operation="reset")

    def step(
        self,
        action: Action,
        *,
        reasoning: Mapping[str, Any] | None = None,
    ) -> Observation:
        """Apply one legal action and return all resulting animation frames."""

        if not self.accepts(action):
            advertised = ", ".join(item.name for item in self.available_actions) or "none"
            raise ActionUnavailableError(
                f"{action.kind.name} is not advertised by the current observation "
                f"(available: {advertised})"
            )

        encoded = self._action_encoder(action)
        payload = _action_payload(action)
        raw = self._wrapper.step(
            encoded,
            data=payload,
            reasoning=dict(reasoning or {}),
        )
        return self._remember(raw, operation=str(action))

    def _remember(self, raw: Any | None, *, operation: str) -> Observation:
        if raw is None:
            raise EmptyObservationError(f"environment returned no observation after {operation}")
        self._latest = _convert_observation(raw)
        return self._latest


def _convert_observation(raw: Any) -> Observation:
    try:
        return Observation.from_sdk(raw)
    except (TypeError, ValueError) as exc:
        raise ArcAdapterError(f"invalid SDK observation: {exc}") from exc


def _action_payload(action: Action) -> dict[str, int]:
    if action.kind is not ActionKind.ACTION6:
        return {}
    assert action.x is not None and action.y is not None
    return {"x": action.x, "y": action.y}


def _encode_official_action(action: Action) -> Any:
    """Create an ``arcengine.GameAction`` only when an action is submitted."""

    try:
        engine = import_module("arcengine")
    except ModuleNotFoundError as exc:
        raise ArcAdapterError(
            "ARC action encoding is unavailable; install the project 'arc' extra "
            "or inject action_encoder"
        ) from exc

    encoded = engine.GameAction.from_id(int(action.kind))
    if action.kind is ActionKind.ACTION6:
        encoded.set_data(_action_payload(action))
    return encoded
