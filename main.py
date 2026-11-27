"""
Mysterious AI - YouTube Shorts auto pipeline

Flow:
1. content_generator.generate_content()  -> topic/title/script/description/tags
2. Voiceover  (edge-tts, fallback gTTS)
3. Images     (Pixabay, fallback gradient backgrounds)
4. Video      (MoviePy, 720x1280, captions drawn with Pillow)
5. Upload     (YouTube Data API, comments ON, not "made for kids")
6. mark_topic_used() sirf upload success ke baad

Env (GitHub Secrets):
  GEMINI_API_KEY_1..15        (content_generator.py use karta hai)
  PIXABAY_API_KEY             (optional, nahi to gradient background)
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Optional env:
  DRY_RUN=1                   video banao par upload mat karo (test ke liye)
  TTS_VOICE                   default en-US-AndrewNeural
"""
import asyncio
import io
import math
import os
import random
import re
import sys
import textwrap
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# Ensure repo root / script directory and common subdirs are on sys.path
BASE_DIR = Path(__file__).resolve().parent
for candidate in (BASE_DIR, BASE_DIR.parent, BASE_DIR / "src", BASE_DIR / "app"):
    if candidate.exists():
        c_str = str(candidate)
        if c_str not in sys.path:
            sys.path.insert(0, c_str)

from content_generator import QuotaExhausted, generate_content, mark_topic_used

W, H = 720, 1280
FPS = 24
SECONDS_PER_IMAGE = 4.5
WORDS_PER_CAPTION = 4
OUT_DIR = str(BASE_DIR / "output")
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AndrewNeural")
DRY_RUN = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "True", "yes")

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


# ---------------- VOICE ----------------
async def _edge_tts(text, path):
    import edge_tts

    communicate = edge_tts.Communicate(text, TTS_VOICE, rate="+5%")
    await asyncio.wait_for(communicate.save(path), timeout=90)


def make_voice(text, path):
    try:
        asyncio.run(_edge_tts(text, path))
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            print("[OK] Voice: edge-tts")
            return path
    except Exception as e:
        print(f"[WARN] edge-tts fail ({str(e)[:100]}), gTTS try kar raha hoon...")

    from gtts import gTTS

    gTTS(text=text, lang="en").save(path)
    print("[OK] Voice: gTTS")
    return path


# ---------------- IMAGES ----------------
def _cover(img, w, h):
    r = max(w / img.width, h / img.height)
    nw, nh = int(img.width * r) + 1, int(img.height * r) + 1
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    img = img.crop((left, top, left + w, top + h))
    # thoda dark karo taake captions saaf dikhein
    return ImageEnhance.Brightness(img).enhance(0.65)


def _gradient(w, h):
    c1 = np.array([random.randint(10, 90) for _ in range(3)], dtype=float)
    c2 = np.array([random.randint(60, 200) for _ in range(3)], dtype=float)
    t = np.linspace(0, 1, h).reshape(h, 1, 1)
    arr = (c1 * (1 - t) + c2 * t) * np.ones((h, w, 1))
    return Image.fromarray(arr.astype("uint8"), "RGB")


def fetch_images(queries, need):
    key = os.environ.get("PIXABAY_API_KEY")
    urls = []
    if key:
        for q in queries:
            if len(urls) >= need:
                break
            try:
                r = requests.get(
                    "https://pixabay.com/api/",
                    params={
                        "key": key,
                        "q": q[:100],
                        "image_type": "photo",
                        "orientation": "vertical",
                        "min_height": 1000,
                        "safesearch": "true",
                        "per_page": 20,
                    },
                    timeout=20,
                )
                r.raise_for_status()
                hits = r.json().get("hits", [])
                random.shuffle(hits)
                for h in hits:
                    u = h.get("largeImageURL")
                    if u and u not in urls:
                        urls.append(u)
            except Exception as e:
                print(f"[WARN] Pixabay '{q}' fail: {str(e)[:100]}")
    else:
        print("[WARN] PIXABAY_API_KEY nahi mili, gradient background use hoga")

    images = []
    for u in urls:
        if len(images) >= need:
            break
        try:
            r = requests.get(u, timeout=30)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            images.append(_cover(img, W, H))
        except Exception as e:
            print(f"[WARN] Image download fail: {str(e)[:100]}")

    while len(images) < need:
        images.append(_gradient(W, H))
    print(f"[OK] Images ready: {len(images)}")
    return images


# ---------------- CAPTIONS ----------------
def _font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def build_captions(script, duration):
    """Script ko 4-4 words ke chunks me todo, audio length ke hisab se time baanto."""
    words = script.split()
    chunks = [
        " ".join(words[i:i + WORDS_PER_CAPTION])
        for i in range(0, len(words), WORDS_PER_CAPTION)
    ]
    weights = [max(len(c), 1) for c in chunks]
    total = float(sum(weights))
    font = _font(56)
    caps, t = [], 0.0
    for chunk, wgt in zip(chunks, weights):
        dur = duration * wgt / total
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        text = "\n".join(textwrap.wrap(chunk, width=16))
        d.multiline_text(
            (W // 2, int(H * 0.60)),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=5,
            stroke_fill=(0, 0, 0, 255),
            anchor="ma",
            align="center",
            spacing=10,
        )
        caps.append((t, t + dur, overlay))
        t += dur
    return caps


# ---------------- VIDEO ----------------
def render_video(content, audio_path, out_path):
    from moviepy.editor import AudioFileClip, VideoClip

    audio = AudioFileClip(audio_path)
    duration = audio.duration + 0.5

    n_img = max(1, math.ceil(duration / SECONDS_PER_IMAGE))
    queries = [str(t) for t in content["tags"]
