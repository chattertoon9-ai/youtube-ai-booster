import os
import sys
import json
import random
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

import google.generativeai as genai

# ---------------- CONFIG ----------------
# Models ki list (priority order). Pehla fail/quota khatam to agla use hoga.
# Env me GEMINI_MODELS="model1,model2" set karke bhi badal sakte ho.
MODELS = [
    m.strip()
    for m in os.environ.get(
        "GEMINI_MODELS",
        "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-3.8-flash",
    ).split(",")
    if m.strip()
]

HISTORY_FILE = "used_topics.json"
QUOTA_FILE = "quota_state.json"   # aaj kaunsi (key, model) exhausted hai
MAX_RETRIES = 4            # naya topic kitni baar try karna hai
MINUTE_RETRIES = 2         # per-minute 429 par kitni baar wait+retry
REQUEST_TIMEOUT = 60       # seconds - Gemini call atak jaye to workflow hang na ho
HISTORY_IN_PROMPT = 40
SIMILARITY_LIMIT = 0.75
REQUIRED_KEYS = ("topic", "title", "script", "description", "tags")

# GEMINI_API_KEY_1 ... GEMINI_API_KEY_15 (jo set hain wahi use honge)
API_KEYS = [
    os.environ[f"GEMINI_API_KEY_{i}"]
    for i in range(1, 16)
    if os.environ.get(f"GEMINI_API_KEY_{i}")
]
if os.environ.get("GEMINI_API_KEY"):
    API_KEYS.append(os.environ["GEMINI_API_KEY"])
API_KEYS = list(dict.fromkeys(API_KEYS))  # duplicate keys hatao
if not API_KEYS:
    raise RuntimeError("Koi GEMINI_API_KEY_* environment variable set nahi hai.")

CATEGORIES = [
    "AI tools", "productivity", "money saving", "tech tips",
    "motivation", "health habits", "study tips", "side income",
    "smartphone tricks", "career growth", "free software", "life hacks",
]

BACKUP_TOPICS = [
    "5 free AI tools that save 3 hours daily",
    "How to use ChatGPT for studying faster",
    "3 phone settings that save battery instantly",
    "Morning habits of highly productive people",
    "How to save money on every purchase",
    "Best free apps for students in 2026",
    "How to learn any skill in 30 days",
    "Top 5 websites that feel illegal to know",
    "How to build a daily routine that sticks",
    "Simple tricks to focus without distractions",
]


# Description ke end me ye line judegi taake log comment karein
COMMENT_CTA = "💬 Comment your suggestion or the next topic you want to see!"


def finalize_description(description, tags):
    """Gemini ke toote hue hashtags hatao, saaf hashtags + comment CTA lagao."""
    body = re.sub(r"\s*#.*$", "", str(description), flags=re.MULTILINE).strip()
    tag_list = []
    for t in tags[:3]:
        clean = re.sub(r"[^A-Za-z0-9]", "", str(t).title())
        if clean:
            tag_list.append("#" + clean)
    tag_list.append("#Shorts")
    return f"{body}\n\n{COMMENT_CTA}\n\n{' '.join(tag_list)}"


class QuotaExhausted(Exception):
    """Sab keys/models ka daily quota khatam."""


# ---------------- HISTORY ----------------
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [str(t) for t in data if str(t).strip()]
    except Exception:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def mark_topic_used(topic):
    """Video upload SUCCESS hone ke baad ye call karo."""
    history = load_history()
    if topic not in history:
        history.append(topic)
        save_history(history)


def normalize(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def is_duplicate(topic, history):
    n = normalize(topic)
    if not n:
        return True
    for old in history:
        o = normalize(old)
        if n == o or SequenceMatcher(None, n, o).ratio() >= SIMILARITY_LIMIT:
            return True
    return False


# ---------------- QUOTA TRACKING ----------------
# Google ka daily quota Pacific time midnight pe reset hota hai
PT = ZoneInfo("America/Los_Angeles")


def _today():
    return datetime.now(PT).strftime("%Y-%m-%d")


def _load_quota():
    try:
        with open(QUOTA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == _today():
            return data
    except Exception:
        pass
    return {"date": _today(), "exhausted": []}


_quota = _load_quota()


def _pair(key, model):
    return f"{key[-6:]}|{model}"


def is_exhausted(key, model):
    return _pair(key, model) in _quota["exhausted"]


def mark_exhausted(key, model):
    p = _pair(key, model)
    if p not in _quota["exhausted"]:
        _quota["exhausted"].append(p)
        try:
            with open(QUOTA_FILE, "w", encoding="utf-8") as f:
                json.dump(_quota, f)
        except Exception:
            pass


def all_exhausted():
    return all(is_exhausted(k, m) for m in MODELS for k in API_KEYS)


def _wait_time(msg, default):
    m = re.search(r"retry in ([\d.]+)s", msg) or re.search(r"seconds:\s*(\d+)", msg)
    return min(float(m.group(1)) + 1, 60) if m else default


def _clean_result(data):
    """Gemini kabhi list deta hai ya keys miss kar deta hai - yahan theek karo."""
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        raise ValueError("Gemini response dict nahi hai")
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(f"Gemini response me keys missing: {missing}")
    if not isinstance(data["tags"], list):
        data["tags"] = [t.strip() for t in str(data["tags"]).split(",") if t.strip()]
    return data


# ---------------- GEMINI (key rotation + model fallback) ----------------
def _gen_config(model_name, temperature):
    cfg = {"response_mime_type": "application/json"}
    # Gemini 3.x models me temperature/top_p/top_k allowed nahi hain, isliye nahi bhejte
    if not model_name.startswith("gemini-3"):
        cfg["temperature"] = temperature
        cfg["top_p"] = 0.95
    return cfg


def ask_gemini(prompt, temperature=1.1):
    """
    Har model ke liye saari keys try karta hai.
    - PerDay quota error  -> (key, model) ko aaj ke liye band, agla try
    - Per-minute 429      -> thoda wait karke same key pe retry
    - 404 (model nahi)    -> poora model skip, agla model
    - Bad JSON / 5xx      -> agla try
    - Sab quota khatam    -> QuotaExhausted
    """
    keys = API_KEYS[:]
    random.shuffle(keys)
    last_err = None

    for model_name in MODELS:
        model_missing = False

        for key in keys:
            if model_missing:
                break
            if is_exhausted(key, model_name):
                continue

            for attempt in range(MINUTE_RETRIES + 1):
                try:
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(
                        model_name,
                        generation_config=_gen_config(model_name, temperature),
                    )
                    response = model.generate_content(
                        prompt,
                        request_options={"timeout": REQUEST_TIMEOUT},
                    )
                    text = response.text.strip()
                    text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
                    return _clean_result(json.loads(text))

                except (json.JSONDecodeError, ValueError) as e:
                    last_err = e
                    print(f"[WARN] Gemini ka response sahi nahi ({e}), agla try...")
                    break

                except Exception as e:
                    last_err = e
                    msg = str(e)
                    is_429 = "429" in msg or "ResourceExhausted" in type(e).__name__

                    if is_429 and "PerDay" in msg:
                        mark_exhausted(key, model_name)
                        print(f"[QUOTA] Daily khatam: ...{key[-6:]} / {model_name}")
                        break

                    if is_429 and attempt < MINUTE_RETRIES:
                        wait = _wait_time(msg, 5 * 2 ** attempt)
                        print(f"[429] Per-minute limit, {wait:.0f}s wait...")
                        time.sleep(wait)
                        continue

                    if "404" in msg or "not found" in msg.lower():
                        print(f"[SKIP] Model available nahi: {model_name} -> {msg[:120]}")
                        model_missing = True
                        break

                    print(f"[WARN] {model_name} fail ({msg[:120]}), agla try...")
                    break

    if all_exhausted():
        raise QuotaExhausted(
            "Sab keys aur models ka daily quota khatam. "
            "Naya project key banao / billing on karo / kal tak ruko."
        )
    raise Exception(f"All Gemini attempts failed: {last_err}")


def build_prompt(history):
    category = random.choice(CATEGORIES)
    seed = random.randint(1, 999999)
    today = datetime.now().strftime("%d %B %Y")
    recent = history[-HISTORY_IN_PROMPT:]

    return f"""
You are a YouTube Shorts content creator.
Today's date: {today}
Category for this video: {category}
Random seed: {seed}

Create ONE brand-new, unique video idea.
The script must end with one short line inviting viewers to comment their suggestions or the next topic they want.

STRICT RULE: Do NOT repeat or closely resemble any of these old topics:
{json.dumps(recent, ensure_ascii=False)}

Return ONLY valid JSON in this exact format:
{{
  "topic": "short unique topic",
  "title": "catchy YouTube title under 70 characters",
  "script": "engaging 100-130 word voiceover script",
  "description": "short video description with 3 hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}
"""


def make_content_from_topic(topic):
    """Backup topic ke liye Gemini se script banwao (topic fix rehta hai)."""
    prompt = f"""
Create a YouTube Shorts package for this topic: "{topic}"
Return ONLY valid JSON:
{{
  "topic": {json.dumps(topic)},
  "title": "catchy title under 70 characters",
  "script": "engaging 100-130 word voiceover script",
  "description": "short description with 3 hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}
"""
    return ask_gemini(prompt, temperature=0.9)


# ---------------- MAIN FUNCTION ----------------
def generate_content(save=True):
    """
    save=True  -> purana behaviour: topic turant history me save (main.py ko badalna nahi padega).
    save=False -> topic save nahi hoga. Upload SUCCESS ke baad
                  mark_topic_used(content["topic"]) call karo (recommended).
    """
    history = load_history()
    content = None

    # Step 1: Gemini se naya topic (retry loop)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            temp = min(1.0 + attempt * 0.07, 1.5)
            result = ask_gemini(build_prompt(history), temperature=temp)
            topic = str(result.get("topic", "")).strip()

            if topic and not is_duplicate(topic, history):
                content = result
                print(f"[OK] New topic found on attempt {attempt}: {topic}")
                break

            print(f"[Retry {attempt}/{MAX_RETRIES}] Duplicate/empty topic: {topic!r}")
        except QuotaExhausted:
            raise
        except Exception as e:
            print(f"[Retry {attempt}/{MAX_RETRIES}] Gemini error: {e}")
        time.sleep(2)

    # Step 2: Fallback - backup topics
    if content is None:
        print("[WARN] Gemini naya topic nahi de paya, backup list try kar raha hoon...")
        unused = [t for t in BACKUP_TOPICS if not is_duplicate(t, history)]
        random.shuffle(unused)
        for topic in unused:
            try:
                content = make_content_from_topic(topic)
                print(f"[OK] Backup topic use hua: {topic}")
                break
            except QuotaExhausted:
                raise
            except Exception as e:
                print(f"[WARN] Backup topic fail: {e}")

    # Step 3: Sab fail
    if content is None:
        raise Exception(
            "No new topic available (Gemini + backup topics dono khatam). "
            "BACKUP_TOPICS mein aur topics add karo ya used_topics.json purana clear karo."
        )

    content["description"] = finalize_description(content.get("description", ""), content["tags"])

    # Step 4: History save (sirf agar save=True)
    if save:
        history.append(content["topic"])
        save_history(history)
    return content


if __name__ == "__main__":
    try:
        print(json.dumps(generate_content(save=False), indent=2, ensure_ascii=False))
    except QuotaExhausted as e:
        print(f"[FATAL] {e}")
        sys.exit(1)  # workflow red dikhe, green nahi
