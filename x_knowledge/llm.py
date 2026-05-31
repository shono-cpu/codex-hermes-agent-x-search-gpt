from __future__ import annotations

import json
import os
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


SETTINGS_PATH = Path("bot_settings.toml")


@dataclass(frozen=True)
class LLMSettings:
    provider: str = "openai"
    quality_mode: str = "max"
    model: str = "gpt-5.5"
    fallback_model: str = "gpt-5.2-pro"
    reasoning_effort: str = "xhigh"
    max_output_tokens: int = 6000
    image_model: str = "gpt-image-1.5"
    image_quality: str = "high"


def load_llm_settings(path: Path = SETTINGS_PATH) -> LLMSettings:
    if not path.exists():
        return LLMSettings()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    llm = raw.get("llm", {}) if isinstance(raw.get("llm", {}), dict) else {}
    image = raw.get("image", {}) if isinstance(raw.get("image", {}), dict) else {}
    return LLMSettings(
        provider=str(llm.get("provider") or "openai"),
        quality_mode=str(llm.get("quality_mode") or "max"),
        model=str(llm.get("model") or "gpt-5.5"),
        fallback_model=str(llm.get("fallback_model") or "gpt-5.2-pro"),
        reasoning_effort=str(llm.get("reasoning_effort") or "xhigh"),
        max_output_tokens=int(llm.get("max_output_tokens") or 6000),
        image_model=str(image.get("model") or "gpt-image-1.5"),
        image_quality=str(image.get("quality") or "high"),
    )


def settings_status(settings: LLMSettings | None = None) -> dict[str, object]:
    settings = settings or load_llm_settings()
    return {
        "provider": settings.provider,
        "quality_mode": settings.quality_mode,
        "model": settings.model,
        "fallback_model": settings.fallback_model,
        "reasoning_effort": settings.reasoning_effort,
        "max_output_tokens": settings.max_output_tokens,
        "image_model": settings.image_model,
        "image_quality": settings.image_quality,
        "api_key_available": bool(os.environ.get("OPENAI_API_KEY")),
    }


def generate_with_openai(prompt: str, system: str, settings: LLMSettings | None = None) -> tuple[str | None, str | None]:
    settings = settings or load_llm_settings()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is not set"
    if settings.provider != "openai":
        return None, f"Unsupported provider: {settings.provider}"

    text, error = request_openai_response(prompt, system, settings, settings.model, api_key)
    if text or not settings.fallback_model or settings.fallback_model == settings.model:
        return text, error
    fallback_text, fallback_error = request_openai_response(prompt, system, settings, settings.fallback_model, api_key)
    if fallback_text:
        return fallback_text, f"Primary model failed ({settings.model}): {error}. Used fallback {settings.fallback_model}."
    return None, f"Primary model failed ({settings.model}): {error}. Fallback failed ({settings.fallback_model}): {fallback_error}"


def request_openai_response(
    prompt: str,
    system: str,
    settings: LLMSettings,
    model: str,
    api_key: str,
) -> tuple[str | None, str | None]:
    payload = {
        "model": model,
        "reasoning": {"effort": settings.reasoning_effort},
        "max_output_tokens": settings.max_output_tokens,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system}]},
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ],
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return None, f"OpenAI API error {exc.code}: {detail[:500]}"
    except Exception as exc:  # noqa: BLE001 - surface API/network errors to the UI.
        return None, str(exc)

    return extract_response_text(data), None


def extract_response_text(data: dict[str, object]) -> str:
    if isinstance(data.get("output_text"), str):
        return str(data["output_text"])
    output = data.get("output")
    parts: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(str(block["text"]))
    return "\n".join(parts).strip()
