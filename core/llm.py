"""
SQLGuardian - LLM transport

The only place in the codebase that talks to a model provider.

Two things this module deliberately does NOT do:
  - decide anything. It returns text or parsed JSON. Verdicts, severities and
    action ordering are computed in core/conditions.py and core/actions.py and
    are never read back from a model response.
  - hardcode a model id. Groq retires models on a published schedule
    (llama-3.3-70b-versatile and llama-3.1-8b-instant were retired 2026-08-16),
    so the id comes from GROQ_MODEL and the default is a current production
    model. Verified against https://console.groq.com/docs/models and against
    GET /openai/v1/models on the account in use.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

import httpx
from loguru import logger

from config.settings import settings


class LLMUnavailable(RuntimeError):
    """Raised when the narration layer cannot be reached or returns nothing usable.

    Callers must treat this as "no narration", never as "no problem". Check
    verdicts are computed before narration is attempted and are unaffected.
    """


def model_id() -> str:
    return settings.groq_model


def is_configured() -> bool:
    return bool(settings.groq_api_key)


def _extract_content(data: Mapping[str, Any]) -> str:
    """Pull assistant text out of a chat completion response.

    Reasoning models (the gpt-oss family included) can return `content: null`
    with the text carried in `reasoning`, and can return a finish_reason of
    "length" with a partial or empty message. Both are normal responses with
    HTTP 200, so neither raise_for_status nor a naive
    data["choices"][0]["message"]["content"] access will catch them.
    """
    choices = data.get("choices") or []
    if not choices:
        raise LLMUnavailable("Model returned no choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")

    if content is None or (isinstance(content, str) and not content.strip()):
        # Some providers put the answer in `reasoning` when content is empty.
        content = message.get("reasoning")

    if content is None or not str(content).strip():
        finish = choices[0].get("finish_reason")
        raise LLMUnavailable(
            f"Model returned empty content (finish_reason={finish!r}, "
            f"model={data.get('model')!r})."
        )

    return str(content)


async def complete(
    prompt: str,
    system: str,
    *,
    json_mode: bool = True,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> str:
    """Send one completion request and return the assistant text.

    Raises LLMUnavailable on any failure. Never returns a partial dict, never
    returns a default verdict.
    """
    if not settings.groq_api_key:
        raise LLMUnavailable("GROQ_API_KEY is not set.")

    payload: dict[str, Any] = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds) as client:
            response = await client.post(
                settings.groq_api_url, headers=headers, json=payload
            )
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"Transport error calling {settings.groq_model}: {exc}") from exc

    if response.status_code >= 400:
        body = response.text[:400]
        # A retired or misspelled model id lands on 404 / model_not_found or
        # model_decommissioned. Name that case explicitly - it is the failure
        # mode that took the app down when llama-3.3-70b-versatile was retired.
        if response.status_code == 404 or "model_not_found" in body or "decommission" in body:
            raise LLMUnavailable(
                f"Model '{settings.groq_model}' was rejected by the provider "
                f"(HTTP {response.status_code}). If it has been retired, set GROQ_MODEL "
                f"to a current id from https://console.groq.com/docs/models. "
                f"Provider said: {body}"
            )
        # Reasoning models spend output tokens before emitting; a max_tokens
        # budget too small for the reasoning pass yields an empty generation,
        # which the provider reports as a JSON validation failure, not a
        # model error. Different fix, so say so.
        if response.status_code == 429:
            raise LLMUnavailable(
                f"Rate limited by the provider on '{settings.groq_model}'. This is a "
                f"quota problem, not a code or model-id problem; reports render without "
                f"narration until it clears. Provider said: {body}"
            )
        if "json_validate_failed" in body:
            raise LLMUnavailable(
                f"Model '{settings.groq_model}' produced no valid JSON. This is usually "
                f"a max_tokens budget too small for a reasoning model, not a bad model id. "
                f"Provider said: {body}"
            )
        raise LLMUnavailable(
            f"Provider returned HTTP {response.status_code}: {response.text[:300]}"
        )

    return _extract_content(response.json())


async def complete_json(
    prompt: str,
    system: str,
    *,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> dict:
    """complete() plus a JSON parse, tolerant of a fenced or prefixed response."""
    raw = await complete(
        prompt, system, json_mode=True, temperature=temperature, max_tokens=max_tokens
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = _salvage_json(raw)
    if not isinstance(parsed, dict):
        raise LLMUnavailable("Model returned JSON that is not an object.")
    return parsed


def _salvage_json(raw: str) -> Any:
    """Recover a JSON object from a response wrapped in prose or a code fence."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMUnavailable(f"Model response was not JSON: {raw[:200]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"Model response was not parseable JSON: {exc}") from exc


async def health() -> dict:
    """Probe used by /health/llm so a retired model is visible before an incident."""
    if not is_configured():
        return {"configured": False, "model": settings.groq_model, "reachable": False,
                "detail": "GROQ_API_KEY is not set."}
    try:
        # Plain text, generous budget: the probe is testing reachability and the
        # model id, not JSON conformance.
        await complete(
            "Reply with the single word: ok",
            "You are a health probe. Answer in one word.",
            json_mode=False,
            max_tokens=512,
        )
        return {"configured": True, "model": settings.groq_model, "reachable": True}
    except LLMUnavailable as exc:
        logger.warning(f"LLM health probe failed: {exc}")
        return {"configured": True, "model": settings.groq_model, "reachable": False,
                "detail": str(exc)}
