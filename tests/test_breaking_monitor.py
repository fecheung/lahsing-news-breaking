import json
import pytest

from breaking_monitor import parse_json_safely, get_guardian_breaking_story


def test_parse_json_safely_plain():
    raw = '[{"a": 1}]'
    out = parse_json_safely(raw)
    assert isinstance(out, list)
    assert out[0]["a"] == 1


def test_parse_json_safely_with_noise():
    raw = 'Some text before\n[{"b": 2}]\nSome text after'
    out = parse_json_safely(raw)
    assert isinstance(out, list)
    assert out[0]["b"] == 2


def test_get_guardian_breaking_story(monkeypatch):
    homepage_html = '<html><body><a data-link-name="article" href="/world/2026/jan/03/breaking-title">Breaking Title</a></body></html>'
    article_html = '<html><head><meta property="og:image" content="https://example.com/img.jpg"/></head><body><article><p>Para1</p><p>Para2</p></article></body></html>'

    class FakeResp:
        def __init__(self, text):
            self.text = text
            self.status_code = 200

    def fake_get(url, headers=None, timeout=None):
        if url == "https://www.theguardian.com/international":
            return FakeResp(homepage_html)
        return FakeResp(article_html)

    monkeypatch.setattr('breaking_monitor.requests.get', fake_get)

    story = get_guardian_breaking_story()
    assert story is not None
    assert story['title'] == 'Breaking Title'
    assert 'Para1' in story['content']
    assert story['imageUrl'] == 'https://example.com/img.jpg'
