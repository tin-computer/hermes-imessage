"""Outbound media: core calls these by keyword with the base-class names.

Claw only takes media as a hosted URL, so http(s) values go to the relay and
local paths go to the base class, which tells the user the file wasn't attached.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from gateway.platforms.base import SendResult


class _FakeWs:
    def __init__(self):
        self.payloads: List[Dict[str, Any]] = []

    async def request(self, payload, timeout=None):
        self.payloads.append(payload)
        return {"ok": True, "messageId": "msg-1"}


@pytest.fixture
def adapter(make_adapter):
    a = make_adapter()
    a._ws = _FakeWs()
    a.notices = []

    async def fake_notice(method, kind, path, chat_id, caption, reply_to, metadata, *, file_name=None):
        a.notices.append((method, kind, path))
        return SendResult(success=False, error="not attached")

    a._send_media_fallback_notice = fake_notice  # type: ignore[assignment]
    return a


def _media_urls(ws: _FakeWs) -> List[str]:
    return [p["url"] for payload in ws.payloads for p in payload["parts"] if p["type"] == "media"]


@pytest.mark.asyncio
async def test_send_image_with_core_keywords(adapter):
    res = await adapter.send_image(
        chat_id="+15551234567", image_url="https://cdn.test/a.png", caption="hi",
        reply_to="m0", metadata={"thread": "t"})
    assert res.success
    assert _media_urls(adapter._ws) == ["https://cdn.test/a.png"]


@pytest.mark.asyncio
async def test_send_voice_with_core_keywords(adapter):
    res = await adapter.send_voice(
        chat_id="+15551234567", audio_path="https://cdn.test/a.m4a", caption=None,
        reply_to=None, metadata={}, is_voice=True)
    assert res.success
    assert _media_urls(adapter._ws) == ["https://cdn.test/a.m4a"]


@pytest.mark.asyncio
async def test_send_video_with_core_keywords(adapter):
    res = await adapter.send_video(
        chat_id="+15551234567", video_path="https://cdn.test/v.mp4", caption="clip",
        reply_to=None, metadata=None, extra="ignored")
    assert res.success
    assert _media_urls(adapter._ws) == ["https://cdn.test/v.mp4"]


@pytest.mark.asyncio
async def test_send_document_with_core_keywords(adapter):
    res = await adapter.send_document(
        chat_id="+15551234567", file_path="https://cdn.test/r.pdf", caption=None,
        file_name="r.pdf", reply_to=None, metadata=None)
    assert res.success
    assert _media_urls(adapter._ws) == ["https://cdn.test/r.pdf"]


@pytest.mark.asyncio
@pytest.mark.parametrize("method, kwargs, kind", [
    ("send_voice", {"audio_path": "/tmp/hermes/voice.ogg", "is_voice": True}, "audio"),
    ("send_video", {"video_path": "/tmp/hermes/clip.mp4"}, "video"),
    ("send_document", {"file_path": "/tmp/hermes/report.pdf", "file_name": "report.pdf"}, "file"),
    ("send_image", {"image_url": "/tmp/hermes/pic.png"}, "image"),
])
async def test_local_paths_are_never_sent_to_the_relay(adapter, method, kwargs, kind):
    res = await getattr(adapter, method)(
        chat_id="+15551234567", caption=None, reply_to=None, metadata=None, **kwargs)
    assert not res.success
    assert adapter._ws.payloads == []
    assert adapter.notices and adapter.notices[0][1] == kind
