"""
content_generator.py - High-retention dark mystery & unexplained phenomena script generator
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
    "gemini-2.0-flash",
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
    "robotics",
    "computer-use",
)


class QuotaExhausted(Exception):
    """Raised when all configured Gemini API keys/models hit quota or rate limits."""


def _get_api_keys() -> list[str]:
    keys: list[str] = []
    for i in range(1, 21):
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
    """Discover text-capable Gemini Flash/Pro models supporting generateContent."""
    discovered: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for api_ver in ("v1beta", "v1"):
        try:
            resp = requests.get(
                f"https://generativelanguage.googleapis.com/{api_ver}/models",
                params={"key": api_key},
                timeout=20,
            )
            if resp.status_code != 200:
                continue
            for item in resp.json().get("models") or []:
                methods = item.get("supportedGenerationMethods") or []
                if "generateContent" not in methods:
                    continue
                model_id = _normalize_model_name(str(item.get("name", "")))
                if not model_id or _is_excluded_model(model_id):
                    continue
                if "gemini" not in model_id.lower():
                    continue
                pair = (api_ver, model_id)
                if pair not in seen:
                    seen.add(pair)
                    discovered.append(pair)
        except Exception:
            continue

    discovered.sort(
        key=lambda x: (
            0 if "flash" in x[1].lower() else 1,
            0 if "2.5" in x[1] else (1 if "2.0" in x[1] else (2 if "1.5" in x[1] else 3)),
            0 if "lite" not in x[1].lower() else 1,
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
    recent = used_topics[-60:]
    avoid_block = ", ".join(recent) if recent else "None"
    return f"""
You are a veteran scriptwriter for a high-retention YouTube Shorts channel focused strictly on dark mysteries, unexplained phenomena, eerie historical anomalies, uncanny survival cases, and unsettling AI or deep-tech mysteries.

Strict Niche & Retention Rules:
- Every single topic MUST focus on mystery, suspense, strange anomalies, or unexplained events.
- NEVER generate DIY tips, lifehacks, money/finance advice, workout tips, generic quotes, or cheerful trivia.
- Open in the first 2 seconds with an immediate hook, escalating tension, and a lingering, eerie final line.
- Write a spoken voiceover script of 38-50 seconds (roughly 105-135 words) in crisp, dramatic English.
- The `script` field must contain ONLY spoken narration—no stage directions, brackets, speaker names, hashtags, or emojis.

Do NOT repeat or closely duplicate any of these already-used topics:
{avoid_block}

Return ONLY a valid JSON object (no markdown fences, no extra prose) matching this schema:
{{
  "topic": "concise mystery or unexplained anomaly topic",
  "title": "high-retention mystery title under 85 chars including #shorts",
  "script": "clean spoken voiceover narration only",
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


def _clean_spoken_script(raw_script: str) -> str:
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", raw_script)
    text = re.sub(r"^(Narrator|Voiceover|Host)\s*:\s*", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _call_gemini(api_key: str, api_ver: str, model: str, prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
        },
    }
    if api_ver == "v1beta":
        payload["generationConfig"]["responseMimeType"] = "application/json"

    resp = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=45,
    )
    if resp.status_code in (429, 403):
        raise QuotaExhausted(f"Key/quota error ({resp.status_code}) on {api_ver}/{model}")
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
    if "#shorts" not in title.lower():
        title = f"{title[:88].strip()} #shorts"

    script = _clean_spoken_script(str(parsed.get("script", "")))
    if len(script.split()) < 35:
        raise ValueError("Generated voiceover script was too short.")

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

    return {
        "topic": topic,
        "title": title[:100],
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

    last_error = None
    quota_hits = 0
    total_attempts = 0

    for key in keys:
        targets = _get_candidate_targets(key)
        for api_ver, model in targets:
            total_attempts += 1
            try:
                result = _call_gemini(key, api_ver, model, prompt)
                if save:
                    mark_topic_used(result["topic"])
                print(f"[INFO] Generated via {api_ver}/{model} -> {result['topic']}")
                return result
            except QuotaExhausted as e:
                quota_hits += 1
                last_error = e
                print(f"[WARN] {e} -> trying next key/model...")
            except Exception as e:
                last_error = e
                print(f"[WARN] Gemini error ({api_ver}/{model}): {str(e)[:140]}")

    if quota_hits > 0 and quota_hits >= total_attempts:
        raise QuotaExhausted(f"All Gemini keys/models hit quota limits. Last error: {last_error}")
    raise RuntimeError(f"Failed to generate content after {total_attempts} attempts. Last error: {last_error}")
