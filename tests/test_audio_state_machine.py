"""Tests for the audio state machine."""

from __future__ import annotations

import time
from unittest.mock import patch

from logs_asmr.audio.state_machine import AudioState, AudioStateMachine


def test_initial_state_is_idle():
    sm = AudioStateMachine()
    assert sm.state == AudioState.IDLE


def test_mute_from_idle():
    sm = AudioStateMachine()
    sm.set_muted(True)
    assert sm.state == AudioState.MUTED


def test_streaming_goes_to_healthy():
    sm = AudioStateMachine()
    sm.set_streaming(True)
    assert sm.state == AudioState.HEALTHY


def test_high_error_rate_goes_to_alarm():
    """Error rate > 1/sec triggers ALARM."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    assert sm.state == AudioState.HEALTHY

    # Feed 11 errors in one batch — rate = 11/10 = 1.1 errors/sec > threshold
    sm.on_error_batch(11)
    assert sm.state == AudioState.ALARM


def test_low_error_rate_goes_to_warning():
    """Error rate > 0 but ≤ 1/sec triggers WARNING."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    assert sm.state == AudioState.HEALTHY

    # Feed 1 error — rate = 1/10 = 0.1 errors/sec (above 0, at or below threshold)
    sm.on_error_batch(1)
    assert sm.state == AudioState.WARNING


def test_no_errors_stays_healthy():
    """Zero errors keeps state at HEALTHY."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(0)
    assert sm.state == AudioState.HEALTHY


def test_exact_threshold_is_warning_not_alarm():
    """Rate exactly at threshold (10 errors / 10s = 1.0) should be WARNING, not ALARM."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(10)  # rate = 10/10 = 1.0, NOT > 1.0
    assert sm.state == AudioState.WARNING


def test_mute_overrides_all():
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(11)
    assert sm.state == AudioState.ALARM
    sm.set_muted(True)
    assert sm.state == AudioState.MUTED


def test_triggers_ignored_when_muted():
    sm = AudioStateMachine()
    sm.set_muted(True)
    assert sm.state == AudioState.MUTED
    sm.on_error_batch(11)
    assert sm.state == AudioState.MUTED


def test_stop_streaming_goes_to_idle():
    sm = AudioStateMachine()
    sm.set_streaming(True)
    assert sm.state == AudioState.HEALTHY
    sm.set_streaming(False)
    assert sm.state == AudioState.IDLE


def test_alarm_cooldown():
    """ALARM should not downgrade until cooldown elapses."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(11)
    assert sm.state == AudioState.ALARM

    # Simulate time passing beyond cooldown — clear error timestamps + set last times in past
    sm._error_timestamps.clear()
    sm._last_high_rate_time = time.monotonic() - 31
    sm._last_any_error_time = time.monotonic() - 31

    with patch("logs_asmr.audio.state_machine.time.monotonic", return_value=time.monotonic()):
        sm._check_cooldown()

    assert sm.state == AudioState.HEALTHY


def test_cooldown_prevents_immediate_downgrade():
    """ALARM should NOT downgrade if cooldown hasn't elapsed even with zero errors."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(11)
    assert sm.state == AudioState.ALARM

    # Clear errors but don't advance time past cooldown
    sm._error_timestamps.clear()

    sm._check_cooldown()
    assert sm.state == AudioState.ALARM  # still in alarm — cooldown not elapsed


def test_warning_cooldown():
    """WARNING should not downgrade to HEALTHY until warning cooldown elapses."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(1)
    assert sm.state == AudioState.WARNING

    # Clear errors but don't advance past cooldown
    sm._error_timestamps.clear()
    sm._check_cooldown()
    assert sm.state == AudioState.WARNING  # still warning — cooldown not elapsed

    # Now advance past cooldown
    sm._last_any_error_time = time.monotonic() - 11
    with patch("logs_asmr.audio.state_machine.time.monotonic", return_value=time.monotonic()):
        sm._check_cooldown()
    assert sm.state == AudioState.HEALTHY


def test_alarm_downgrades_to_warning_if_errors_remain():
    """ALARM should downgrade to WARNING (not HEALTHY) if low-rate errors persist."""
    sm = AudioStateMachine()
    sm.set_streaming(True)
    sm.on_error_batch(11)
    assert sm.state == AudioState.ALARM

    # Reduce to low rate (keep 1 recent timestamp) and advance past cooldown
    now = time.monotonic()
    sm._error_timestamps = [now]
    sm._last_high_rate_time = now - 31
    sm._last_any_error_time = now

    with patch("logs_asmr.audio.state_machine.time.monotonic", return_value=now):
        sm._check_cooldown()

    assert sm.state == AudioState.WARNING


def test_triggers_ignored_when_idle():
    """Error batches should be ignored when not streaming."""
    sm = AudioStateMachine()
    assert sm.state == AudioState.IDLE
    sm.on_error_batch(11)
    assert sm.state == AudioState.IDLE
