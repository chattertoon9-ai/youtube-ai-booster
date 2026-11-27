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

DEFAULT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


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


def _get_models() -> list[str]:
    raw = os.environ.get("GEMINI_MODELS", "").strip()
    if not raw:
        return DEFAULT_MODELS
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or DEFAULT_MODELS


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
  "tags": ["dark mystery", "unexplained", "mystery shorts", "strange history", "creepy facts"]
}}
""".strip()


def _extract_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response did not contain a valid JSON object.")
    return json.loads(cleaned[start : end + 1])


def _call_gemini(api_key: str, model: str, prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "responseMimeType": "application/json",
        },
    }
    resp = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=45,
    )
    if resp.status_code in (429, 403):
        raise QuotaExhausted(f"Key/quota error ({resp.status_code}) on model {model}")
    resp.raise_for_status()

    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("Empty candidates from Gemini API.")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    raw_text = "".join(str(p.get("text", "")) for p in parts).strip()
    if not raw_text:
        raise ValueError("Empty text response from Gemini API.")

    parsed = _extract_json_object(raw_text)
    topic = str(parsed.get("topic", "")).strip() or "Unexplained Anomaly"
    title = str(parsed.get("title", "")).strip() or f"{topic} #shorts"
    script = str(parsed.get("script", "")).strip()
    description = (
        str(parsed.get("description", "")).strip()
        or f"{title}\n\n#shorts #mystery #unexplained"
    )
    raw_tags = parsed.get("tags")
    tags = (
        [str(t).strip() for t in raw_tags if str(t).strip()]
        if isinstance(raw_tags, list)
        else ["dark mystery", "unexplained", "mystery shorts", "shorts"]
    )

    if not script:
        raise ValueError("Generated script was empty.")

    return {
        "topic": topic,
        "title": title,
        "script": script,
        "description": description,
        "tags": tags,
    }


def generate_content(save: bool = False) -> dict:
    keys = _get_api_keys()
    if not keys:
        raise QuotaExhausted("No GEMINI_API_KEY_1..15 or GEMINI_API_KEY found in environment.")

    used_topics = _load_used_topics()
    prompt = _build_prompt(used_topics)
    models = _get_models()

    last_error = None
    quota_hits = 0
    total_attempts = len(keys) * len(models)

    for key in keys:
        for model in models:
            try:
                result = _call_gemini(key, model, prompt)
                if save:
                    mark_topic_used(result["topic"])
                return result
            except QuotaExhausted as e:
                quota_hits += 1
                last_error = e
                print(f"[WARN] {e} -> trying next key/model...")
            except Exception as e:
                last_error = e
                print(f"[WARN] Gemini error ({model}): {str(e)[:120]}")

    if quota_hits > 0 and quota_hits >= total_attempts:
        raise QuotaExhausted(f"All Gemini keys/models hit quota limits. Last error: {last_error}")
    raise RuntimeError(f"Failed to generate content after {total_attempts} attempts. Last error: {last_error}")
