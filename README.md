# Logs ASMR

[![PyPI](https://img.shields.io/pypi/v/logs-asmr)](https://pypi.org/project/logs-asmr/)
[![Python](https://img.shields.io/pypi/pyversions/logs-asmr)](https://pypi.org/project/logs-asmr/)
[![License](https://img.shields.io/github/license/justinGrosvenor/logs-asmr)](https://github.com/justinGrosvenor/logs-asmr/blob/main/LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/justinGrosvenor/logs-asmr/publish.yml)](https://github.com/justinGrosvenor/logs-asmr/actions)

A desktop log streaming workspace with ambient audio that reacts to your error rate. Calm ocean waves when things are healthy, rain when errors trickle in, full thunderstorm when it hits the fan.

## Install

```bash
pip install logs-asmr
```

## Quick Start

```bash
logs-asmr --fake   # demo mode with synthetic logs
```

## Log Sources

Connect to logs from multiple backends:

- **AWS CloudWatch** — browse log groups and streams
- **Docker** — tail container logs
- **Kubernetes** — stream pod logs
- **GCP Cloud Logging** — Google Cloud logs
- **Grafana Loki** — WebSocket streaming
- **systemd journald** — system journal (Linux)
- **File / stdin** — tail local files

## Audio

Three ambient tracks crossfade based on error rate over a 10-second sliding window:

| Error Rate | Sound | Track |
|---|---|---|
| 0 errors/sec | Ocean waves | `beach.opus` |
| > 0 and ≤ 1/sec | Rain + distant thunder | `rain_thunder.opus` |
| > 1/sec | Full thunderstorm | `thunderstorm.opus` |

A white noise floor smooths transitions between tracks. Cooldown timers (30s for alarm, 10s for warning) prevent flip-flopping when error rates fluctuate.

Swap in your own sounds from Settings > Audio — any `.wav`, `.mp3`, or `.opus` file works. Night mode (auto-detected from system dark mode) cuts volume by half.

## Filtering

A slide-out filter drawer with live-updating results:

- **Text include/exclude** with optional regex
- **Level chips** — toggle ERROR, WARN, INFO, DEBUG
- **Component chips** — auto-discovered from log fields (`service`, `component`, `logger`, etc.)
- **Filter presets** — save and load per log group

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Pause / resume live tail |
| `M` | Mute / unmute audio |
| `Ctrl+F` | Open filter drawer |
| `Ctrl+L` | Clear log view |
| `Escape` | Close filter drawer |

## Performance

- 10,000-event ring buffer with overflow detection
- 100ms processing ticks with batched rendering
- Up to 50,000 lines retained in the viewport
- Live event rate and drop count in the status bar
