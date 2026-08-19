"""
Provider-agnostic LLM client.

The agent calls `complete(messages, temperature)` and receives text. Which
provider answers is a construction-time choice, so the model is an
experimental variable rather than an architectural commitment.

Both backends are implemented over plain HTTPS with the standard library —
no provider SDKs — so the dependency surface stays small and the request
format is fully visible in this file.

Token usage is recorded per call and accumulated, because measuring real
per-run cost is itself one of the study's outputs.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, inp: int, out: int) -> None:
        self.input_tokens += inp
        self.output_tokens += out
        self.calls += 1


@dataclass
class LLMClient:
    provider: str            # "gemini" | "anthropic"
    model: str
    usage: Usage = field(default_factory=Usage)
    timeout_s: int = 120
    max_retries: int = 3

    def complete(self, system: str, messages: list[dict], temperature: float = 0.0) -> str:
        """messages: [{"role": "user"|"assistant", "content": str}, ...] -> text."""
        for attempt in range(self.max_retries):
            try:
                if self.provider == "gemini":
                    return self._gemini(system, messages, temperature)
                if self.provider == "anthropic":
                    return self._anthropic(system, messages, temperature)
                raise ValueError(f"unknown provider: {self.provider}")
            except urllib.error.HTTPError as e:
                # 429/5xx: back off and retry; anything else is a real error.
                if e.code in (429, 500, 502, 503) and attempt < self.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                body = e.read().decode(errors="replace")[:500]
                raise RuntimeError(f"{self.provider} HTTP {e.code}: {body}") from e
            except urllib.error.URLError as e:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise RuntimeError(f"{self.provider} unreachable: {e}") from e
        raise RuntimeError("retries exhausted")

    # ---- Gemini ------------------------------------------------------------

    def _gemini(self, system: str, messages: list[dict], temperature: float) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.model}:generateContent?key={key}")
        contents = [
            {"role": "user" if m["role"] == "user" else "model",
             "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json",
            },
        }
        data = self._post(url, {}, payload)
        meta = data.get("usageMetadata", {})
        self.usage.add(meta.get("promptTokenCount", 0), meta.get("candidatesTokenCount", 0))
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"gemini: unexpected response shape: {json.dumps(data)[:300]}") from e

    # ---- Anthropic ---------------------------------------------------------

    def _anthropic(self, system: str, messages: list[dict], temperature: float) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": temperature,
            "system": system,
            "messages": messages,
        }
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }
        data = self._post("https://api.anthropic.com/v1/messages", headers, payload)
        u = data.get("usage", {})
        self.usage.add(u.get("input_tokens", 0), u.get("output_tokens", 0))
        try:
            return "".join(b["text"] for b in data["content"] if b["type"] == "text")
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"anthropic: unexpected response shape: {json.dumps(data)[:300]}") from e

    # ---- shared ------------------------------------------------------------

    def _post(self, url: str, headers: dict, payload: dict) -> dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.load(resp)


def from_env() -> LLMClient:
    """Build a client from LLM_PROVIDER / LLM_MODEL, defaulting to Gemini Flash."""
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    default_model = {
        "gemini": "gemini-2.5-flash",
        "anthropic": "claude-haiku-4-5",
    }[provider]
    model = os.environ.get("LLM_MODEL", default_model)
    return LLMClient(provider=provider, model=model)
