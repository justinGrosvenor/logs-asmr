"""Loki tail connections must use maintained roots and strict TLS verification."""

from __future__ import annotations

import asyncio
import ssl

import certifi
import pytest
import websockets

from logs_asmr.connectors.loki.worker import LokiTailWorker
from logs_asmr.models.source import Source
from logs_asmr.streaming.ring_buffer import RingBuffer


class EmptyConnection:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


@pytest.mark.parametrize("secure", [False, True])
def test_loki_tail_tls_policy(monkeypatch, secure):
    calls = []

    def connect(uri, **kwargs):
        calls.append((uri, kwargs))
        return EmptyConnection()

    monkeypatch.setattr(websockets, "connect", connect)
    source = Source(
        connector="loki",
        params={
            "url": "https://loki.example" if secure else "http://localhost:3100",
            "org_id": "tenant-1",
        },
    )
    worker = LokiTailWorker(RingBuffer(capacity=16), source)
    asyncio.run(worker._stream())

    uri, options = calls[0]
    assert uri.startswith("wss://" if secure else "ws://")
    assert options["additional_headers"] == {"X-Scope-OrgID": "tenant-1"}
    if secure:
        context = options["ssl"]
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        maintained_roots = ssl.create_default_context(cafile=certifi.where())
        assert set(context.get_ca_certs(binary_form=True)) == set(
            maintained_roots.get_ca_certs(binary_form=True)
        )
    else:
        assert "ssl" not in options
