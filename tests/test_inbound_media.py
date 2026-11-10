"""Inbound media handling tests.

The Claw Messenger relay pushes attachments as ``{url, mimeType}`` objects.
The adapter downloads them and caches via Hermes' built-in helpers so they
become local file paths the agent's vision tools can read.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, List
from unittest.mock import AsyncMock

import pytest


# A tiny but valid PNG (1×1 red pixel) so cache_image_from_bytes accepts it
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "89000000017352474200aece1ce90000000d49444154789c63faff9f1100000000"
    "0049454e44ae426082"
)


class _FakeStream:
    def __init__(self, body: bytes, content_type: str = "image/png", chunk: int = 1 << 20):
        self._body, self._chunk = body, chunk
        self.headers = {"content-type": content_type}
        self.bytes_read = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    async def aiter_bytes(self):
        for i in range(0, len(self._body), self._chunk):
            piece = self._body[i:i + self._chunk]
            self.bytes_read += len(piece)
            yield piece


class _FakeHttp:
    def __init__(self, body: bytes = _PNG_BYTES):
        self.body = body
        self.requested: List[str] = []
        self.last_stream = None

    def stream(self, method, url):
        assert method == "GET"
        self.requested.append(url)
        self.last_stream = _FakeStream(self.body)
        return self.last_stream

    async def aclose(self):
        return None


async def _receive(fake_server, make_adapter, monkeypatch, attachments, http):
    from hermes_claw_messenger import adapter as adapter_mod

    captured: List[Any] = []

    async def handler(ws, srv):
        await ws.send(json.dumps({
            "type": "message", "from": "+15551234567",
            "text": "look", "messageId": "m1",
            "isGroup": False,
            "attachments": attachments,
        }))
        async for _ in ws:
            pass

    async with fake_server(handler=handler) as srv:
        adapter = make_adapter(server_url=srv.url)

        async def fake_handle(event):
            captured.append(event)
        adapter.handle_message = fake_handle  # type: ignore[assignment]

        # Force the adapter to use our fake httpx client
        monkeypatch.setattr(adapter_mod, "httpx", type("X", (), {
            "AsyncClient": lambda *a, **kw: http,
        }))

        assert await adapter.connect() is True
        await asyncio.sleep(0.5)
        await adapter.disconnect()

    assert len(captured) == 1
    return captured[0]


@pytest.mark.asyncio
async def test_inbound_image_is_downloaded_and_cached(fake_server, make_adapter,
                                                     monkeypatch):
    """An inbound message with an image attachment should produce a
    MessageEvent whose ``media_urls`` points at a real cached path."""
    ev = await _receive(fake_server, make_adapter, monkeypatch, [{
        "url": "https://example.test/img.png", "mimeType": "image/png",
    }], _FakeHttp())

    assert ev.media_urls, "media should have been downloaded"
    assert ev.media_types[0].startswith("image/")
    # The cached path should be an absolute file path
    assert ev.media_urls[0].endswith(".png")


@pytest.mark.asyncio
async def test_inbound_attachment_over_cap_stops_streaming(fake_server, make_adapter,
                                                          monkeypatch):
    """A body past 20 MB is abandoned mid-stream, not read whole first."""
    from hermes_claw_messenger.adapter import MAX_INBOUND_MEDIA_SIZE

    http = _FakeHttp(body=b"\0" * (MAX_INBOUND_MEDIA_SIZE * 2))
    ev = await _receive(fake_server, make_adapter, monkeypatch, [{
        "url": "https://example.test/huge.png", "mimeType": "image/png",
    }], http)

    assert ev.media_urls == []
    assert http.last_stream.bytes_read <= MAX_INBOUND_MEDIA_SIZE + (1 << 20)


@pytest.mark.asyncio
async def test_inbound_attachment_must_be_https(fake_server, make_adapter, monkeypatch):
    http = _FakeHttp()
    ev = await _receive(fake_server, make_adapter, monkeypatch, [
        {"url": "http://example.test/img.png", "mimeType": "image/png"},
        {"url": "file:///etc/passwd", "mimeType": "text/plain"},
    ], http)

    assert http.requested == []
    assert ev.media_urls == []
