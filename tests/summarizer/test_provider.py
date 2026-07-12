"""
tests/summarizer/test_provider.py
agents/summarizer/provider.py (OllamaProvider, LLMCompletion, LLMProviderError,
resolve_ollama_host, _default_post_json) のテスト。

実Ollamaへのネットワーク呼び出しは一切行わない。OllamaProvider経由のテストは
すべてfake transport (callable) で、_default_post_json単体のテストは
urllib.request.urlopenのmonkeypatchで代替する (実ソケット通信は発生しない)。
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from agents.summarizer.provider import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_TIMEOUT_SECONDS,
    LLMCompletion,
    LLMProviderError,
    OllamaProvider,
    _default_post_json,
    resolve_ollama_host,
)


class _RecordingTransport:
    """呼び出し引数を記録し、既定応答または例外を返すfake transport。"""

    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict, float]] = []

    def __call__(self, url: str, payload: dict, timeout: float):
        self.calls.append((url, payload, timeout))
        if self.error is not None:
            raise self.error
        return self.response


class _FakeHTTPResponse:
    """urllib.request.urlopen()が返すcontext managerを模したfake。"""

    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


# ----------------------------------------------------------------
# (1) OllamaProvider.generate() 正常系: text抽出・metadata・payload内容
# ----------------------------------------------------------------


def test_generate_extracts_text_and_metadata():
    transport = _RecordingTransport(response={"response": "こんにちは", "done": True})
    provider = OllamaProvider(model="llama3", transport=transport)

    result = provider.generate("prompt")

    assert isinstance(result, LLMCompletion)
    assert result.text == "こんにちは"
    assert result.model_name == "llama3"
    assert result.provider_name == "ollama"
    assert result.duration_ms is not None
    assert result.duration_ms >= 0
    assert result.raw_response == {"response": "こんにちは", "done": True}


def test_generate_sends_expected_payload_defaults():
    transport = _RecordingTransport(response={"response": "ok"})
    provider = OllamaProvider(
        model="llama3", host="http://example:11434", transport=transport
    )

    provider.generate("hello")

    url, payload, _timeout = transport.calls[0]
    assert url == "http://example:11434/api/generate"
    assert payload == {"model": "llama3", "prompt": "hello", "stream": False}


def test_generate_format_json_sets_format_field():
    transport = _RecordingTransport(response={"response": "{}"})
    provider = OllamaProvider(model="llama3", transport=transport)

    provider.generate("prompt", format_json=True)

    _url, payload, _timeout = transport.calls[0]
    assert payload["format"] == "json"


def test_generate_system_sets_system_field():
    transport = _RecordingTransport(response={"response": "ok"})
    provider = OllamaProvider(model="llama3", transport=transport)

    provider.generate("prompt", system="You are helpful")

    _url, payload, _timeout = transport.calls[0]
    assert payload["system"] == "You are helpful"


def test_generate_without_system_or_format_json_omits_fields():
    transport = _RecordingTransport(response={"response": "ok"})
    provider = OllamaProvider(model="llama3", transport=transport)

    provider.generate("prompt")

    _url, payload, _timeout = transport.calls[0]
    assert "system" not in payload
    assert "format" not in payload
    assert "options" not in payload


def test_generate_passes_options():
    transport = _RecordingTransport(response={"response": "ok"})
    options = {"temperature": 0.2}
    provider = OllamaProvider(model="llama3", options=options, transport=transport)

    provider.generate("prompt")

    _url, payload, _timeout = transport.calls[0]
    assert payload["options"] == {"temperature": 0.2}


def test_generate_options_dict_is_copied_not_aliased():
    transport = _RecordingTransport(response={"response": "ok"})
    options = {"temperature": 0.2}
    provider = OllamaProvider(model="llama3", options=options, transport=transport)
    options["temperature"] = 0.9  # constructor後にmutateしても影響しないこと

    provider.generate("prompt")

    _url, payload, _timeout = transport.calls[0]
    assert payload["options"] == {"temperature": 0.2}


# ----------------------------------------------------------------
# (2) timeout引き渡し・model必須
# ----------------------------------------------------------------


def test_generate_passes_custom_timeout_seconds():
    transport = _RecordingTransport(response={"response": "ok"})
    provider = OllamaProvider(model="llama3", timeout_seconds=45.0, transport=transport)

    provider.generate("prompt")

    _url, _payload, timeout = transport.calls[0]
    assert timeout == 45.0


def test_generate_default_timeout_is_at_least_120_seconds():
    assert DEFAULT_TIMEOUT_SECONDS >= 120.0
    transport = _RecordingTransport(response={"response": "ok"})
    provider = OllamaProvider(model="llama3", transport=transport)

    provider.generate("prompt")

    _url, _payload, timeout = transport.calls[0]
    assert timeout == DEFAULT_TIMEOUT_SECONDS


def test_model_is_required_and_rejects_empty_string():
    with pytest.raises(ValueError):
        OllamaProvider(model="")


# ----------------------------------------------------------------
# (3) host解決順: 引数 > OLLAMA_HOST環境変数 > 既定値、scheme補完
# ----------------------------------------------------------------


def test_resolve_host_prefers_explicit_argument(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://env-host:11434")
    assert resolve_ollama_host("http://arg-host:9999") == "http://arg-host:9999"


def test_resolve_host_falls_back_to_env_var(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://env-host:11434")
    assert resolve_ollama_host() == "http://env-host:11434"


def test_resolve_host_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_ollama_host() == DEFAULT_OLLAMA_HOST


def test_resolve_host_adds_scheme_when_env_has_no_scheme(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "ollama:11434")
    assert resolve_ollama_host() == "http://ollama:11434"


def test_resolve_host_adds_scheme_when_argument_has_no_scheme(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_ollama_host("myhost:1234") == "http://myhost:1234"


def test_resolve_host_strips_trailing_slash(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_ollama_host("http://localhost:11434/") == "http://localhost:11434"


def test_provider_uses_resolved_host_in_generate_url(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "envhost:1111")
    transport = _RecordingTransport(response={"response": "ok"})
    provider = OllamaProvider(model="llama3", transport=transport)

    provider.generate("prompt")

    url, _payload, _timeout = transport.calls[0]
    assert url == "http://envhost:1111/api/generate"


def test_provider_host_property_reflects_resolution(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    provider = OllamaProvider(model="llama3")
    assert provider.host == DEFAULT_OLLAMA_HOST
    assert provider.model == "llama3"


# ----------------------------------------------------------------
# (4) エラー正規化 (transport経由): 接続失敗・空応答
# ----------------------------------------------------------------


def test_generate_wraps_unexpected_transport_exception_as_provider_error():
    transport = _RecordingTransport(error=ConnectionError("boom"))
    provider = OllamaProvider(model="llama3", transport=transport)

    with pytest.raises(LLMProviderError):
        provider.generate("prompt")


def test_generate_propagates_llm_provider_error_from_transport_unchanged():
    transport = _RecordingTransport(error=LLMProviderError("connection failed"))
    provider = OllamaProvider(model="llama3", transport=transport)

    with pytest.raises(LLMProviderError, match="connection failed"):
        provider.generate("prompt")


def test_generate_raises_on_empty_response_text():
    transport = _RecordingTransport(response={"response": ""})
    provider = OllamaProvider(model="llama3", transport=transport)

    with pytest.raises(LLMProviderError):
        provider.generate("prompt")


def test_generate_raises_on_missing_response_field():
    transport = _RecordingTransport(response={"done": True})
    provider = OllamaProvider(model="llama3", transport=transport)

    with pytest.raises(LLMProviderError):
        provider.generate("prompt")


def test_generate_raises_when_response_body_is_not_a_dict():
    transport = _RecordingTransport(response=["not", "a", "dict"])
    provider = OllamaProvider(model="llama3", transport=transport)

    with pytest.raises(LLMProviderError):
        provider.generate("prompt")


# ----------------------------------------------------------------
# (5) LLMCompletion.to_provenance_kwargs()
# ----------------------------------------------------------------


def test_llm_completion_to_provenance_kwargs():
    completion = LLMCompletion(text="x", model_name="llama3", provider_name="ollama")
    assert completion.to_provenance_kwargs() == {
        "model_provider": "ollama",
        "model_name": "llama3",
    }


# ----------------------------------------------------------------
# (6) _default_post_json 単体テスト (urllib.request.urlopenをmonkeypatch、
#     実ネットワーク通信は発生しない)
# ----------------------------------------------------------------


def test_default_post_json_success(monkeypatch):
    def fake_urlopen(request, timeout):
        assert timeout == 30.0
        return _FakeHTTPResponse(json.dumps({"response": "hi"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = _default_post_json("http://localhost:11434/api/generate", {"a": 1}, 30.0)
    assert result == {"response": "hi"}


def test_default_post_json_sends_post_with_json_body(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["content_type"] = request.get_header("Content-type")
        return _FakeHTTPResponse(json.dumps({"response": "ok"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    _default_post_json("http://localhost:11434/api/generate", {"model": "llama3"}, 30.0)

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["method"] == "POST"
    assert captured["body"] == {"model": "llama3"}
    assert captured["content_type"] == "application/json"


def test_default_post_json_http_error_5xx_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(b"server exploded"),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError, match="HTTP 500"):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_default_post_json_http_error_4xx_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url="http://localhost:11434/api/generate",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b"not found"),
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError, match="HTTP 404"):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_default_post_json_connection_failure_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError, match="Failed to connect"):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_default_post_json_timeout_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError, match="timed out"):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_default_post_json_invalid_json_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        return _FakeHTTPResponse(b"not json{{{")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError, match="not valid JSON"):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_default_post_json_empty_body_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        return _FakeHTTPResponse(b"")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_default_post_json_non_object_json_is_normalized(monkeypatch):
    def fake_urlopen(request, timeout):
        return _FakeHTTPResponse(b"[1, 2, 3]")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(LLMProviderError, match="not a JSON object"):
        _default_post_json("http://localhost:11434/api/generate", {}, 30.0)


def test_provider_generate_end_to_end_with_patched_urlopen_uses_stream_false(
    monkeypatch,
):
    # デフォルトtransport (_default_post_json) がOllamaProvider経由で実際に
    # 呼ばれる経路も、urlopenのmonkeypatchのみでネットワークなしに検証する。
    captured = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeHTTPResponse(json.dumps({"response": "ok"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = OllamaProvider(model="llama3", host="http://localhost:11434")
    result = provider.generate("hi")

    assert result.text == "ok"
    assert captured["body"]["stream"] is False
