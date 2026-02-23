# Logs ASMR — Minimal Spec

## Product Goal
Make CloudWatch Logs feel **local, fast, and trustworthy**.

This is **not** a query console.  
This is a **live log workspace** with strong filtering, real backpressure, and optional audio cues that help—not distract.

Primary use case:
> “I’m running a system, I want to see what’s happening now and notice when it’s broken without babysitting graphs.”

---

## Core Principles
- Fast > clever
- Filters, not queries
- Never lie to the user (drops, delays, limits are visible)
- Everything important is one click away
- Audio is assistive, silent by default, and easy to kill

---

## Layout

### Left Pane — Sources
Filesystem-style tree:
- Account
- Region
- Log Group
- Optional Log Stream

Behaviors:
- Switching sources preserves current filters
- Recently used sources pinned at top
- Virtualized lists only

---

### Top Action Strip (always visible)
Controls:
- Tail / Pause
- Clear
- Filter Drawer
- Mute (large, persistent)
- Status indicators:
  - Live
  - Paused
  - Dropping
  - Muted

No hidden advanced menus.

---

### Main View — Log Stream
- Virtualized, append-only view
- Monospace
- Timestamp | Level | Message
- Collapsible repeated lines

Behaviors:
- Auto-scroll when live
- Freeze view on pause
- Copy/select behaves like local file
- Optional level highlighting

---

## Filters

### Mandatory Filters
- Include (text or regex)
- Exclude (text or regex)
- Level chips: ERROR, WARN, INFO, DEBUG
- Component / Service chips (auto-extracted)
- Time mode: Live, Paused, Recent window
- Filter presets (per project / log group)

Rules:
- Filters apply immediately
- No Apply button
- Drawer is non-modal

---

## Streaming & Backpressure

### Threading Model
- Network thread consumes CloudWatch Live Tail
- Bounded in-memory buffer
- UI renders at fixed cadence

### Backpressure Rules
- Drop oldest events when buffer is full
- Visible drop counter
- Dropping status badge
- Catch-up button clears buffer and resumes live

Invariant:
User is never unaware of dropped logs.

---

## Audio System

### Global Rules
- Muted by default
- Big mute button
- Hotkey toggle
- Per-sound volume controls

### Audio Modes
1. Ocean / Thunder
2. Rain / Thunk

### Audio Layers
- Ambient: very quiet, healthy-only
- Alert: short, unmistakable, rate-limited
- Warning: off by default, extremely subtle

Audio triggers only if log lines pass filters.

---

## Accessibility
- Audio never required
- Visual indicators always present
- Night mode auto-reduces audio
- Office-safe defaults

---

## Explicit Non-Goals
- No Logs Insights queries
- No dashboards
- No metrics graphs
- No alarm authoring
- No AI explanations

---

## Stretch Goals
- Export visible logs
- Per-project workspaces
- Keyboard-first navigation
- Minimal read-only alarm timeline

---

## Implementation Notes (PyQt6)

### Widget Structure
- QMainWindow
- TopActionBar
- QSplitter: SourceTree | LogView
- Custom virtualized log viewport
- Non-modal filter drawer

### Audio State Machine
States:
- Muted
- Healthy
- Alarm

Transitions are state-driven, not event-spam-driven.

---

End of spec.
