"""Audio manager — three severity layers with crossfade transitions.

Layers:
  noise_floor.opus  — constant quiet white noise bed (smooths all transitions)
  beach.opus        — calm ocean waves (HEALTHY, no errors)
  rain_thunder.opus — rain + distant thunder (WARNING, few errors)
  thunderstorm.opus — full thunderstorm (ALARM, many errors)

Crossfades between the three severity tracks based on log error rate.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from logs_asmr.audio.state_machine import AudioStateMachine
from logs_asmr.constants import (
    APP_DIR,
    CROSSFADE_DURATION_MS,
    CROSSFADE_STEP_MS,
    NIGHT_MODE_VOLUME_FACTOR,
)

logger = logging.getLogger("logs_asmr.audio.manager")

_AUDIO_DIR = Path(__file__).parent.parent / "resources" / "audio"
_CUSTOM_SOUND_DIR = APP_DIR / "sounds"

SOUND_SLOTS = ["healthy", "warning", "alarm", "noise_floor"]
DEFAULT_FILES = ["beach.opus", "rain_thunder.opus", "thunderstorm.opus", "noise_floor.opus"]

_READY_STATUSES = (
    QMediaPlayer.MediaStatus.LoadedMedia,
    QMediaPlayer.MediaStatus.BufferedMedia,
)

_NOISE_FLOOR_VOLUME = 0.08


class AudioManager(QObject):
    """Three severity tracks + noise floor with crossfade transitions."""

    def __init__(
        self,
        state_machine: AudioStateMachine,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sm = state_machine
        self._volume = 0.33
        self._night_mode = False
        self._loaded = False
        self._want_playing = False

        # Three severity tracks: beach, rain_thunder, thunderstorm
        # Current volume for each (0.0–1.0, before night factor)
        self._track_vols = [0.0, 0.0, 0.0]

        # Crossfade state
        self._fade_timer = QTimer(self)
        self._fade_timer.setInterval(CROSSFADE_STEP_MS)
        self._fade_timer.timeout.connect(self._fade_step)
        self._fade_steps_remaining = 0
        self._goals = [0.0, 0.0, 0.0]
        self._deltas = [0.0, 0.0, 0.0]

        # Lazy-loaded players: [beach, rain_thunder, thunderstorm]
        self._players: list[QMediaPlayer | None] = [None, None, None]
        self._outputs: list[QAudioOutput | None] = [None, None, None]
        self._noise_player: QMediaPlayer | None = None
        self._noise_output: QAudioOutput | None = None

        # Connect state machine signals
        self._sm.state_changed.connect(self._on_state_changed)

    # --- Lazy loading ---

    def _make_player(self) -> tuple[QMediaPlayer, QAudioOutput]:
        output = QAudioOutput(self)
        output.setVolume(0.0)
        player = QMediaPlayer(self)
        player.setAudioOutput(output)
        # Manual looping via EndOfMedia signal — avoids Qt's internal seek-loop
        # which spams "Could not update timestamps" warnings with FFmpeg backend.
        player.mediaStatusChanged.connect(
            lambda s, p=player: self._on_media_status(p, s)
        )
        return player, output

    def _resolve_path(self, slot_index: int) -> Path:
        """Return custom file if present in APP_DIR/sounds/, else bundled default."""
        slot = SOUND_SLOTS[slot_index]
        if _CUSTOM_SOUND_DIR.exists():
            for candidate in _CUSTOM_SOUND_DIR.iterdir():
                if candidate.stem == slot and candidate.is_file():
                    return candidate
        return _AUDIO_DIR / DEFAULT_FILES[slot_index]

    def _load_source(self, player: QMediaPlayer, slot_index: int) -> None:
        path = self._resolve_path(slot_index)
        if path.exists():
            player.setSource(QUrl.fromLocalFile(str(path)))
        else:
            logger.warning("Audio file not found: %s", path)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        for i in range(3):
            player, output = self._make_player()
            self._players[i] = player
            self._outputs[i] = output
            self._load_source(player, i)

        # Noise floor (slot index 3)
        self._noise_player, self._noise_output = self._make_player()
        self._load_source(self._noise_player, 3)

        logger.info("Audio loaded: healthy / warning / alarm + noise floor")

    def _on_media_status(
        self, player: QMediaPlayer, status: QMediaPlayer.MediaStatus
    ) -> None:
        if not self._want_playing:
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Manual loop: restart from beginning
            player.setPosition(0)
            player.play()
            return
        if player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            return
        if status in _READY_STATUSES:
            player.play()
            logger.debug("Player auto-started: %s", player.source().fileName())

    # --- Volume helpers ---

    def _night_factor(self) -> float:
        return NIGHT_MODE_VOLUME_FACTOR if self._night_mode else 1.0

    def _apply_volumes(self) -> None:
        f = self._night_factor()
        for i, output in enumerate(self._outputs):
            if output:
                output.setVolume(self._track_vols[i] * f)
        if self._noise_output:
            vol = _NOISE_FLOOR_VOLUME * f if self._want_playing else 0.0
            self._noise_output.setVolume(vol)

    # --- Crossfade engine ---

    def _crossfade_to(self, goals: list[float]) -> None:
        steps = max(1, CROSSFADE_DURATION_MS // CROSSFADE_STEP_MS)
        self._fade_steps_remaining = steps
        self._goals = list(goals)
        self._deltas = [
            (goals[i] - self._track_vols[i]) / steps for i in range(3)
        ]
        self._fade_timer.start()

    def _fade_step(self) -> None:
        self._fade_steps_remaining -= 1
        if self._fade_steps_remaining <= 0:
            self._track_vols = list(self._goals)
            self._fade_timer.stop()
            # Pause players that faded to zero to avoid decoding at silence
            for i in range(3):
                if self._goals[i] == 0.0 and self._players[i] is not None:
                    self._players[i].pause()
            # If all severity tracks are silent, also pause noise floor
            if all(g == 0.0 for g in self._goals) and self._noise_player is not None:
                self._noise_player.pause()
        else:
            for i in range(3):
                self._track_vols[i] += self._deltas[i]
        for i in range(3):
            self._track_vols[i] = max(0.0, min(1.0, self._track_vols[i]))
        self._apply_volumes()

    # --- State machine handlers ---

    def _on_state_changed(self, state: str) -> None:
        """Crossfade to the appropriate sound for the new state."""
        if state == "healthy":
            self._ensure_loaded()
            self._want_playing = True
            self._start_all()
            self._crossfade_to([self._volume, 0.0, 0.0])
            logger.debug("Crossfading to beach")
        elif state == "warning":
            self._ensure_loaded()
            self._want_playing = True
            self._start_all()
            self._crossfade_to([0.0, self._volume, 0.0])
            logger.debug("Crossfading to rain+thunder")
        elif state == "alarm":
            self._ensure_loaded()
            self._want_playing = True
            self._start_all()
            self._crossfade_to([0.0, 0.0, self._volume])
            logger.debug("Crossfading to thunderstorm")
        elif state in ("idle", "muted"):
            if not self._loaded:
                return
            self._want_playing = False
            self._apply_volumes()
            self._crossfade_to([0.0, 0.0, 0.0])
            logger.debug("Fading all audio out")

    def _start_all(self) -> None:
        all_players = [*self._players, self._noise_player]
        for player in all_players:
            if not player:
                continue
            status = player.mediaStatus()
            playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
            if not playing and status in (
                *_READY_STATUSES,
                QMediaPlayer.MediaStatus.EndOfMedia,
            ):
                player.play()

    # --- Public API ---

    @property
    def volume(self) -> float:
        return self._volume

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        # Update whichever track is currently the goal
        new_goals = [
            self._volume if self._goals[i] > 0 else 0.0 for i in range(3)
        ]
        self._crossfade_to(new_goals)

    def set_night_mode(self, enabled: bool) -> None:
        self._night_mode = enabled
        self._apply_volumes()

    def current_filename(self, slot_index: int) -> str:
        """Return the display filename for a slot (custom or default)."""
        path = self._resolve_path(slot_index)
        return path.name

    def set_sound(self, slot_index: int, source_path: str | Path) -> bool:
        """Copy a custom sound file into APP_DIR/sounds/ and hot-swap the player.

        Returns True on success, False on error.
        """
        source_path = Path(source_path)
        _CUSTOM_SOUND_DIR.mkdir(parents=True, exist_ok=True)

        # Remove any existing custom file for this slot
        slot = SOUND_SLOTS[slot_index]
        to_delete = [f for f in _CUSTOM_SOUND_DIR.iterdir() if f.stem == slot]
        for f in to_delete:
            f.unlink()

        try:
            dest = _CUSTOM_SOUND_DIR / f"{slot}{source_path.suffix}"
            shutil.copy(source_path, dest)
        except OSError:
            logger.exception("Failed to copy sound file for %s: %s", slot, source_path)
            return False

        logger.info("Custom sound set for %s: %s", slot, dest)
        self._reload_slot(slot_index)
        return True

    def reset_sound(self, slot_index: int) -> None:
        """Remove the custom sound file for a slot, reverting to the bundled default."""
        slot = SOUND_SLOTS[slot_index]
        if _CUSTOM_SOUND_DIR.exists():
            to_delete = [f for f in _CUSTOM_SOUND_DIR.iterdir() if f.stem == slot]
            for f in to_delete:
                f.unlink()
                logger.info("Custom sound removed for %s: %s", slot, f)

        self._reload_slot(slot_index)

    def _reload_slot(self, slot_index: int) -> None:
        """Hot-swap a single slot's source while preserving playback state."""
        if not self._loaded:
            return

        player = self._players[slot_index] if slot_index < 3 else self._noise_player

        if player is None:
            return

        was_playing = player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        player.stop()
        self._load_source(player, slot_index)

        if was_playing and self._want_playing:
            # Source isn't ready yet — _on_media_status will auto-start it
            pass
