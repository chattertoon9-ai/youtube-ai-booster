"""
content_generator.py - Dark mystery & unexplained intrigue content generator for YouTube Shorts
"""
import json
import os
import re
from pathlib import Path
import requests

BASE_DIR = Path(__file__).resolve().parent
USED_TOPICS_FILE = BASE_DIR / "used_topics.json"

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

EXCLUDED_MODEL_TOKENS = (
    "-tts",
    "-image",
    "-audio",
    "imagen",
    "veo",
    "embedding",
    "aqa",
)


class QuotaExhausted(Exception):
    """Raised when all configured Gemini API keys/models hit quota or rate limits."""


def _get_api_keys() -> list[str]:
    keys: list[str] = []
    for i in range(1, 16):
        val = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
        if val and val not in keys:
            keys.append(val)
    single = os.environ.get("GEMINI_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    return keys


def _normalize_model_name(name: str) -> str:
    cleaned = name.strip()
    if cleaned.startswith("models/"):
        cleaned = cleaned[len("models/") :]
    return cleaned


def _is_excluded_model(model_id: str) -> bool:
    lower = model_id.lower()
    return any(token in lower for token in EXCLUDED_MODEL_TOKENS)


def _discover_models(api_key: str) -> list[tuple[str, str]]:
    """Query ListModels on v1beta and v1 to find text-capable models supporting generateContent."""
    discovered: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for api_ver in ("v1beta", "v1"):
        try:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models"
            resp = requests.get(url, params={"key": api_key}, timeout=20)
            if resp.status_code != 200:
                continue
            for item in resp.json().get("models") or []:
                methods = item.get("supportedGenerationMethods") or []
                if "generateContent" not in methods:
                    continue
                model_id = _normalize_model_name(str(item.get("name", "")))
                if not model_id or _is_excluded_model(model_id):
                    continue
                if "flash" not in model_id.lower():
                    continue
                pair = (api_ver, model_id)
                if pair not in seen:
                    seen.add(pair)
                    discovered.append(pair)
        except Exception:
            continue

    discovered.sort(
        key=lambda x: (
            0 if "2.5" in x[1] else (1 if "2.0" in x[1] else (2 if "1.5" in x[1] else 3)),
            0 if "lite" not in x[1] else 1,
            0 if x[0] == "v1beta" else 1,
            x[1],
        )
    )
    return discovered


def _get_candidate_targets(api_key: str) -> list[tuple[str, str]]:
    raw = os.environ.get("GEMINI_MODELS", "").strip()
    if raw:
        custom = [_normalize_model_name(m) for m in raw.split(",") if m.strip()]
        return [("v1beta", m) for m in custom] + [("v1", m) for m in custom]

    discovered = _discover_models(api_key)
    if discovered:
        return discovered

    targets: list[tuple[str, str]] = []
    for m in FALLBACK_MODELS:
        targets.append(("v1beta", m))
        targets.append(("v1", m))
    return targets


def _load_used_topics() -> list[str]:
    if not USED_TOPICS_FILE.exists():
        return []
    try:
        data = json.loads(USED_TOPICS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return []


def _save_used_topics(topics: list[str]) -> None:
    USED_TOPICS_FILE.write_text(
        json.dumps(topics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def mark_topic_used(topic: str) -> None:
    cleaned = str(topic or "").strip()
    if not cleaned:
        return
    topics = _load_used_topics()
    if cleaned.lower() not in {t.lower() for t in topics}:
        topics.append(cleaned)
        _save_used_topics(topics)


def _build_prompt(used_topics: list[str]) -> str:
    recent = used_topics[-50:]
    avoid_block = ", ".join(recent) if recent else "None"
    return f"""
You are a scriptwriter for a YouTube Shorts channel focused strictly on dark mysteries, unexplained phenomena, eerie historical events, uncanny survival stories, and unsettling AI or technology anomalies.

Strict Niche Rules:
- Every topic MUST revolve around mystery, suspense, strange anomalies, or unexplained events.
- NEVER generate DIY hacks, lifehacks, money hustles, fitness tips, generic motivation, or lighthearted trivia.
- Keep the tone atmospheric, suspenseful, and factual/intriguing without graphic violence or policy violations.
- Write a 35-50 second spoken voiceover script (roughly 95-130 words) in vivid, punchy English that hooks viewers in the first 2 seconds and ends with an eerie or thought-provoking twist.

Do NOT repeat or closely duplicate any of these already-used topics:
{avoid_block}

Return ONLY valid JSON (no markdown fences, no commentary) with this exact structure:
{{
  "topic": "concise dark mystery or unexplained intrigue topic",
  "title": "high-retention mystery title under 85 chars with #shorts",
  "script": "spoken voiceover lines only, no stage directions, speaker labels, or emojis",
  "description": "suspenseful YouTube Shorts description with 3-5 hashtags including #shorts #mystery #unexplained",
