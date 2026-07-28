"""Lazy, provenance-guarded construction of one official offline environment."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock

from arcworld.env.arc_adapter import ArcAdapter, ArcAdapterError
from arcworld.env.provenance import (
    EnvironmentProvenance,
    collect_environment_provenance,
)
from arcworld.types import Action, Observation

_loaded_source_hashes: dict[Path, str] = {}
_loaded_source_lock = RLock()


@dataclass(slots=True)
class DeferredOfflineEnvironment:
    """Delay SDK/scorecard creation until the controller's explicit start phase."""

    game_id: str
    environments_dir: Path
    recordings_dir: Path
    seed: int
    expected_provenance: EnvironmentProvenance
    save_recording: bool = True
    _adapter: ArcAdapter | None = field(default=None, init=False, repr=False)
    _initial: Observation | None = field(default=None, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.environments_dir = self.environments_dir.expanduser().resolve()
        self.recordings_dir = self.recordings_dir.expanduser().resolve()

    def start(self) -> Observation:
        with self._lock:
            if self._initial is not None:
                return self._initial
            current = collect_environment_provenance(self.environments_dir, self.game_id)
            if current != self.expected_provenance:
                raise ArcAdapterError("environment assets changed before the test started")
            _claim_source_identity(current)
            adapter = ArcAdapter.open_offline(
                self.game_id,
                environments_dir=self.environments_dir,
                recordings_dir=self.recordings_dir,
                seed=self.seed,
                save_recording=self.save_recording,
            )
            observation = adapter.start()
            if observation.game_id != self.game_id:
                raise ArcAdapterError(
                    f"SDK opened game_id {observation.game_id!r}, expected {self.game_id!r}"
                )
            _verify_wrapper_directory(adapter, current)
            after = collect_environment_provenance(self.environments_dir, self.game_id)
            if after != current:
                raise ArcAdapterError("environment assets changed while the SDK loaded them")
            self._adapter = adapter
            self._initial = observation
            return observation

    def reset(self) -> Observation:
        with self._lock:
            return self._require_adapter().reset()

    def step(self, action: Action) -> Observation:
        with self._lock:
            return self._require_adapter().step(action)

    def _require_adapter(self) -> ArcAdapter:
        if self._adapter is None:
            raise RuntimeError("official environment has not started")
        return self._adapter


def _claim_source_identity(provenance: EnvironmentProvenance) -> None:
    """Fail closed if the SDK may cache older bytes for the same source path."""

    path = provenance.source.path.resolve()
    with _loaded_source_lock:
        prior = _loaded_source_hashes.get(path)
        if prior is not None and prior != provenance.source.sha256:
            raise ArcAdapterError(
                "environment source changed after this process loaded the same path; "
                "restart the GUI before starting another test"
            )
        _loaded_source_hashes[path] = provenance.source.sha256


def _verify_wrapper_directory(
    adapter: ArcAdapter,
    provenance: EnvironmentProvenance,
) -> None:
    info = getattr(adapter.raw_wrapper, "info", None)
    raw_local_dir = getattr(info, "local_dir", None)
    if not isinstance(raw_local_dir, str):
        raise ArcAdapterError("SDK wrapper does not expose its resolved local environment path")
    actual = Path(raw_local_dir).expanduser().resolve()
    expected = provenance.metadata.path.parent.resolve()
    if actual != expected:
        raise ArcAdapterError(
            f"SDK loaded environment directory {actual}, expected provenance directory {expected}"
        )
