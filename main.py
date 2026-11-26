import os
import json
import random
import re
import time
from datetime import datetime
from difflib import SequenceMatcher

import google.generativeai as genai

# ---------------- CONFIG ----------------
MODEL_NAME = "gemini-3.8-flash"
HISTORY_FILE = "used_topics.json"
MAX_RETRIES = 8            # kitni baar naya topic try karna hai
HISTORY_IN_PROMPT = 40     # prompt mein sirf last 40 topics bhejo
SIMILARITY_LIMIT = 0.75    # isse zyada similar = duplicate

# GEMINI_API_KEY_1 ... GEMINI_API_KEY_15 (jo set hain wahi use honge)
API_KEYS = [
    os.environ[f"GEMINI_API_KEY_{i}"]
    for i in range(1, 16)
    if os.environ.get(f"GEMINI_API_KEY_{i}")
]
if os.environ.get("GEMINI_API_KEY"):
    API_KEYS.append(os.environ["GEMINI_API_KEY"])
if not API_KEYS:
    raise RuntimeError("Koi GEMINI_API_KEY_* environment variable set nahi hai.")

CATEGORIES = [
    "AI tools", "productivity", "money saving", "tech tips",
    "motivation", "health habits", "study tips", "side income",
    "smartphone tricks", "career growth", "free software", "life hacks",
]

# Gemini fail ho jaye to ye backup topics use honge
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


# ---------------- GEMINI (key rotation) ----------------
def ask_gemini(prompt, temperature=1.1):
    """Keys ko shuffle karke ek-ek try karta hai. Quota/error par agli key."""
    keys = API_KEYS[:]
    random.shuffle(keys)
    last_err = None

    for key in keys:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                MODEL_NAME,
                generation_config={
                    "temperature": temperature,
                    "top_p": 0.95,
                    "response_mime_type": "application/json",
                },
            )
            text = model.generate_content(prompt).text.strip()
            text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()
            return json.loads(text)
        except Exception as e:
            last_err = e
            print(f"[WARN] Key fail ({str(e)[:80]}), agli key try kar raha hoon...")
            continue

    raise Exception(f"All Gemini keys failed: {last_err}")


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
  "topic": "{topic}",
  "title": "catchy title under 70 characters",
  "script": "engaging 100-130 word voiceover script",
  "description": "short description with 3 hashtags",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"]
}}
"""
    return ask_gemini(prompt, temperature=0.9)


# ---------------- MAIN FUNCTION ----------------
def generate_content():
    history = load_history()
    content = None

    # Step 1: Gemini se naya topic lene ki koshish (retry loop)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            temp = min(1.0 + attempt * 0.07, 1.5)
            result = ask_gemini(build_prompt(history), temperature=temp)
            topic = result.get("topic", "").strip()

            if topic and not is_duplicate(topic, history):
                content = result
                print(f"[OK] New topic found on attempt {attempt}: {topic}")
                break

            print(f"[Retry {attempt}/{MAX_RETRIES}] Duplicate/empty topic: {topic!r}")
        except Exception as e:
            print(f"[Retry {attempt}/{MAX_RETRIES}] Gemini error: {e}")
        time.sleep(2)

    # Step 2: Fallback - backup topics list
    if content is None:
        print("[WARN] Gemini naya topic nahi de paya, backup list try kar raha hoon...")
        unused = [t for t in BACKUP_TOPICS if not is_duplicate(t, history)]
        random.shuffle(unused)
        for topic in unused:
            try:
                content = make_content_from_topic(topic)
                print(f"[OK] Backup topic use hua: {topic}")
                break
            except Exception as e:
                print(f"[WARN] Backup topic fail: {e}")

    # Step 3: Sab fail hone par hi exception
    if content is None:
        raise Exception(
            "No new topic available (Gemini + backup topics dono khatam). "
            "BACKUP_TOPICS mein aur topics add karo ya used_topics.json purana clear karo."
        )

    # Step 4: History mein save karo
    history.append(content["topic"])
    save_history(history)
    return content


if __name__ == "__main__":
    print(json.dumps(generate_content(), indent=2, ensure_ascii=False))
