"""
DKB Summarizer - LLM Provider
Ollama provider呼び出し本体
(docs/architecture/06_AI/Story_Summary_Generation_Plan.md §9
 `summary-generation-provider-implementation`)。

ユーザーが2026-07-13にsummarizer系のLLM provider実装を明示的に解禁したことを
受けて実装する（`AI_CONTEXT.md` §4。`agents/extractor/`のLLM呼び出し本体は
引き続き未解禁のまま）。本モジュールはOllama `/api/generate`呼び出しの
最小実装のみを扱い、prompt設計・要約生成ロジック自体は次PR
`summary-generation-prompt-implementation`のスコープとする。

配置方針: `agents/common/`共有レイヤーは新設せず、summarizer固有にこの
モジュールを置く（`Story_Summary_Generation_Plan.md` §7.2/§11で確定。
`agents/extractor/`側のLLM呼び出しが解禁されるタイミングで、共通レイヤーへの
昇格要否を再判断する）。

新規ランタイム依存は追加しない（`pyproject.toml`の`dependencies = []`を
維持する）。HTTP呼び出しは標準ライブラリ`urllib.request`のみで実装する。

テスト容易性のため、HTTP transport（`post_json(url, payload, timeout) -> dict`
相当のcallable）をconstructor injectionできる設計にしている。本モジュール自体の
テスト（`tests/summarizer/test_provider.py`）・本PR作業中とも、実Ollamaへの
ネットワーク呼び出しは一切行わない（fake transportのみを使う）。

APIキー・認証は扱わない（ローカルOllamaのみが対象。外部provider(API系)は
opt-inで将来PRに委ねる、`Story_Summary_Generation_Plan.md` §3）。

docs/architecture/06_AI/Story_Summary_Generation_Plan.md
agents/summarizer/models.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

# host解決の既定値 (Story_Summary_Generation_Plan.md §3、docker-compose.ymlの
# ollamaサービスはコンテナ内から`http://ollama:11434`だが、host側で
# デフォルト値を明示しない呼び出しはローカル既定値を使う)。
DEFAULT_OLLAMA_HOST = "http://localhost:11434"

# 要約生成はレスポンスが遅いことを踏まえ、120秒以上を既定にする。
DEFAULT_TIMEOUT_SECONDS: float = 120.0

OLLAMA_GENERATE_PATH = "/api/generate"

# HTTP transportのシグネチャ。constructor injection用
# (url, payload, timeout_seconds) -> レスポンスJSONをdictにしたもの。
PostJsonFn = Callable[[str, dict[str, Any], float], dict[str, Any]]


class LLMProviderError(Exception):
    """LLM provider呼び出し失敗を正規化する例外。

    接続失敗・HTTPエラー・応答JSON不正・空応答のいずれもこの例外に正規化する。
    **自動retryは実装しない**（呼び出し側の将来判断に委ねる、
    `Story_Summary_Generation_Plan.md` §9 本PRのスコープ外）。
    """


@dataclass
class LLMCompletion:
    """LLM生成結果 + 監査用metadata。

    `agents/summarizer/models.py`の`SummaryProvenance`へ変換しやすい形にする
    (`to_provenance_kwargs()`)。
    """

    text: str
    model_name: str
    provider_name: str
    duration_ms: int | None = None
    raw_response: dict[str, Any] | None = None

    def to_provenance_kwargs(self) -> dict[str, Any]:
        """`SummaryProvenance(**kwargs)`に渡せる部分的なkwargsを返す。

        `model_provider`/`model_name`のみを埋める。`prompt_version`/
        `generated_at`/`input_refs`は呼び出し側 (prompt実装PR) が
        別途設定する。
        """
        return {
            "model_provider": self.provider_name,
            "model_name": self.model_name,
        }


class SummaryLLMProvider(ABC):
    """Story/Episode Summary生成用のLLM provider抽象。"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format_json: bool = False,
    ) -> LLMCompletion:
        """promptからテキストを生成する。"""
        raise NotImplementedError


def resolve_ollama_host(host: str | None = None) -> str:
    """Ollama hostを解決する。

    優先順位: 引数 > `OLLAMA_HOST`環境変数 > 既定値(`DEFAULT_OLLAMA_HOST`)。
    scheme無し (`host:port`形式) の場合は`http://`を補う。末尾の`/`は除去する。
    """
    resolved = host or os.environ.get("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST
    resolved = resolved.strip()
    if "://" not in resolved:
        resolved = f"http://{resolved}"
    return resolved.rstrip("/")


def _default_post_json(
    url: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    """`urllib.request`を使った既定のHTTP transport。

    接続失敗・HTTPエラー・応答JSON不正のいずれも`LLMProviderError`へ正規化する。
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise LLMProviderError(
            f"Ollama returned HTTP {exc.code} from {url}: {body[:500]}"
        ) from exc
    except TimeoutError as exc:
        raise LLMProviderError(
            f"Ollama request to {url} timed out after {timeout}s"
        ) from exc
    except urllib.error.URLError as exc:
        raise LLMProviderError(
            f"Failed to connect to Ollama at {url}: {exc.reason}"
        ) from exc

    try:
        decoded = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LLMProviderError(f"Ollama response from {url} was not UTF-8") from exc

    try:
        parsed = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise LLMProviderError(
            f"Ollama response from {url} was not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise LLMProviderError(
            f"Ollama response from {url} was not a JSON object "
            f"(got {type(parsed).__name__})"
        )
    return parsed


class OllamaProvider(SummaryLLMProvider):
    """ローカルOllama (`POST {host}/api/generate`, `stream: false`固定) 経由の
    provider。

    APIキー・認証は扱わない（ローカルOllamaのみが対象、
    `Story_Summary_Generation_Plan.md` §3の固定premise）。opt-inの外部
    provider (API系) は将来PRで別クラスとして追加する想定。
    """

    def __init__(
        self,
        model: str,
        *,
        host: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        options: dict[str, Any] | None = None,
        transport: PostJsonFn | None = None,
    ) -> None:
        if not model:
            raise ValueError("OllamaProvider requires a non-empty model name")
        self._model = model
        self._host = resolve_ollama_host(host)
        self._timeout_seconds = timeout_seconds
        self._options = dict(options) if options else None
        self._transport: PostJsonFn = transport or _default_post_json

    @property
    def model(self) -> str:
        return self._model

    @property
    def host(self) -> str:
        return self._host

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        format_json: bool = False,
    ) -> LLMCompletion:
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
        }
        if system is not None:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"
        if self._options:
            payload["options"] = self._options

        url = f"{self._host}{OLLAMA_GENERATE_PATH}"
        start = time.monotonic()
        try:
            response_body = self._transport(url, payload, self._timeout_seconds)
        except LLMProviderError:
            raise
        except Exception as exc:
            # transportが自前のLLMProviderError以外を送出した場合(fake transport
            # によるOSError等のシミュレーションを含む)も、呼び出し側からは常に
            # LLMProviderErrorとして観測できるよう正規化する。
            raise LLMProviderError(f"Ollama transport failed: {exc}") from exc
        duration_ms = int((time.monotonic() - start) * 1000)

        if not isinstance(response_body, dict):
            raise LLMProviderError(
                "Ollama response was not a JSON object "
                f"(got {type(response_body).__name__})"
            )

        text = response_body.get("response")
        if not text:
            raise LLMProviderError(
                "Ollama response contained no non-empty 'response' text"
            )

        return LLMCompletion(
            text=text,
            model_name=self._model,
            provider_name="ollama",
            duration_ms=duration_ms,
            raw_response=response_body,
        )
