"""
Mysterious AI - Cinematic YouTube Shorts Auto Pipeline (v2)

Flow:
 1. Gemini  -> JSON (title, SEO description, tags, hook, 6-8 scenes with image keywords)
 2. Pixabay -> one relevant image PER scene (not one image for the whole video)
 3. Edge-TTS (neural voice, gTTS fallback) -> one voice clip per scene (perfect sync)
 4. Cinematic Ken-Burns zoom/pan + vignette + color grade + dip transitions
 5. Word-by-word style captions (3 words at a time, big, yellow/white, outlined)
 6. Generated dark ambient drone + heartbeat music (no download needed)
 7. Upload to YouTube with SEO title/description/hashtags/tags + engagement comment
"""

import os
import re
import json
import time
import random
import asyncio
import shutil
import wave
import traceback
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from gtts import gTTS

from moviepy import (
    VideoClip,
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
)

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
W, H = 1080, 1920
BASE_W, BASE_H = int(W * 1.3), int(H * 1.3)  # oversized image so we can zoom/pan
FPS = 30
WORK = Path("work")
HISTORY_FILE = Path("used_topics.json")
VOICE = os.environ.get("TTS_VOICE", "en-US-ChristopherNeural")
DRY_RUN = os.environ.get("DRY_RUN", "1") == "1"

CATEGORIES = [
    "a disturbing historical secret most people never learned",
    "a bizarre fact about the human body",
    "a real unsolved mystery",
    "a terrifying fact about the deep ocean",
    "a space phenomenon that sounds fake but is real",
    "a dark psychology trick that affects everyone",
    "a forgotten ancient civilization or lost technology",
    "a strange animal ability that feels like science fiction",
    "a dark true story from history that was covered up",
    "a mind-bending physics or time fact",
    "a creepy fact about the internet, technology or AI",
    "a strange natural place on Earth that looks impossible",
]

FOCUS_SEEDS = [
    "ancient Egypt", "Medieval Europe", "Cold War", "Japan", "the Amazon", "the Arctic",
    "Ancient Rome", "the Middle East", "the Pacific Ocean", "Victorian era", "Soviet Union",
    "India", "Africa", "the Moon and Mars", "World War 2", "the human brain", "the Sahara",
    "China", "South America", "the Bermuda region", "volcanoes", "caves", "insects", "viruses",
]

GENERIC_QUERIES = [
    "dark mystery", "ancient ruins", "night sky", "foggy forest",
    "old library", "ocean storm", "abandoned building", "galaxy",
]


# ----------------------------------------------------------------------------
# History (avoid repeating topics)
# ----------------------------------------------------------------------------
def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_history(title):
    hist = load_history()
    hist.append(title)
    HISTORY_FILE.write_text(json.dumps(hist[-80:], ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# 1. Content generation (Gemini)
# ----------------------------------------------------------------------------
def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found")
    return json.loads(text[start:end + 1])


def valid(data):
    scenes = data.get("scenes")
    return (
        isinstance(scenes, list)
        and len(scenes) >= 4
        and all(isinstance(s, dict) and s.get("narration", "").strip() for s in scenes)
        and data.get("title")
    )


def build_prompt(category, recent, focus):
    recent_txt = "; ".join(recent[-25:]) if recent else "none"
    return f"""
You are a viral YouTube Shorts scriptwriter and YouTube SEO expert for a faceless
"Mysterious AI" facts & mysteries channel.

Topic angle for THIS video: {category}.
Strong preference: connect it to {focus} (skip this only if no true, verifiable fact exists).
Already used topics (never repeat or closely resemble): {recent_txt}

RULES
- Facts must be TRUE and verifiable. Never invent statistics, names or quotes.
- 6 to 8 scenes. Total narration 85-110 words. Each scene 1-2 short punchy sentences (max 22 words).
- Scene 1 = pattern-interrupt hook (shocking claim or question), max 14 words, no greetings, no "Did you know".
- Build curiosity: reveal the answer gradually, strongest fact in the middle.
- Last scene = cliffhanger line that flows back into scene 1 (so the Short loops) plus a short question
  inviting comments.
- Each scene needs "search": 2-3 English words for a stock photo that matches visually
  (concrete objects/places like "ancient temple", "deep ocean", "human brain" - never abstract words).
- title: max 60 characters, curiosity gap, main keyword near the front, exactly one emoji, no hashtags.
- description: 2-3 sentences with natural search keywords about the topic.
- hashtags: 4 single-word hashtags without '#'.
- tags: 12 SEO keyword phrases people actually search on YouTube.
- hook_text: max 5 words, ALL CAPS, shown on screen in the first seconds.
- comment: one engaging question to post as the first comment.

Return ONLY valid JSON in this exact shape:
{{
  "title": "",
  "description": "",
  "hashtags": ["", "", "", ""],
  "tags": [""],
  "hook_text": "",
  "comment": "",
  "scenes": [{{"narration": "", "search": ""}}]
}}
"""


def too_similar(title, history):
    words = lambda t: set(re.findall(r"[a-z]{4,}", t.lower()))
    a = words(title)
    for old in history:
        b = words(old)
        if a and b and len(a & b) / len(a | b) >= 0.4:
            return True
    return False


STORY_TRUE = [
    "a real person who survived something that should have been impossible",
    "a real historical betrayal or conspiracy with a shocking twist",
    "a real disappearance or case that is still unexplained",
    "a real scientist or inventor whose discovery was ignored or stolen",
    "a real spy, heist or escape that sounds like a movie",
    "a real moment in history when the world almost ended by accident",
    "a real ordinary person whose life changed in one strange day",
]
STORY_FICTION = [
    "a short creepy mystery story with a chilling twist ending",
    "a short sci-fi story where a tiny discovery changes everything",
    "a short psychological thriller told in first person",
    "a short urban-legend style story with an unexpected final line",
]


def build_story_prompt(kind, category, recent, focus):
    recent_txt = "; ".join(recent[-25:]) if recent else "none"
    if kind == "true":
        truth = ("This must be a REAL, verifiable story. Use only facts you are certain about. "
                 "If unsure about a name, date or number, leave it out or stay general. Never invent quotes.")
    else:
        truth = ("This is an ORIGINAL FICTIONAL story. Do not present it as real, do not use real people's names.")
    return f"""
You are a viral YouTube Shorts storyteller and YouTube SEO expert for a faceless
"Mysterious AI" storytelling channel.

Story type: {category}.
Setting inspiration: {focus} (optional, only if it fits).
Already used stories (never repeat or resemble): {recent_txt}
{truth}

STORY STRUCTURE (very important for retention)
1. HOOK (scene 1, max 12 words): put the viewer in the middle of the danger/mystery. No greetings.
2. SETUP (1-2 scenes): who, where, what is at stake, in the simplest words.
3. ESCALATION (4-6 scenes): each scene must raise tension or reveal something new. Every scene ends
   making the viewer want the next one.
4. TWIST (1-2 scenes): the surprising turn or revelation.
5. ENDING (last scene): a short, powerful line that echoes the hook so the Short loops, plus a question
   inviting comments.

STYLE
- 10 to 14 scenes. Total narration 120-150 words. Each scene 1-2 sentences, max 16 words, simple spoken English.
- Short sentences, vivid verbs, present or past tense consistently. No filler, no "in this video".
- Each scene needs "search": 2-3 English words for a stock photo that fits visually
  (concrete: "abandoned hospital", "snowy mountain", "old letter", "dark corridor").
- title: max 60 chars, curiosity gap, one emoji, main keyword first, no hashtags.
- description: 2-3 sentences with natural search keywords.
- hashtags: 4 single-word hashtags without '#'.
- tags: 12 SEO phrases people search on YouTube.
- hook_text: max 5 words, ALL CAPS.
- comment: one question that makes people argue or guess in the comments.
- story_type: "true" or "fiction".

Return ONLY valid JSON in this exact shape:
{{
  "title": "", "description": "", "hashtags": ["", "", "", ""], "tags": [""],
  "hook_text": "", "comment": "", "story_type": "{kind}",
  "scenes": [{{"narration": "", "search": ""}}]
}}
"""


def get_fallback():
    return {
        "title": "You Age Slower on Top Floors? ⏳",
        "description": "Einstein's general relativity says time runs faster the higher you are. "
                       "Learn the strange physics behind it.",
        "hashtags": ["facts", "science", "mystery", "physics"],
        "tags": ["time dilation", "general relativity", "science facts", "mind blowing facts",
                 "einstein", "physics explained", "shocking facts"],
        "hook_text": "TIME IS NOT CONSTANT",
        "comment": "Would you move to the top floor to age slower? 👇",
        "scenes": [
            {"narration": "You are aging slower right now, and the floor you stand on proves it.", "search": "skyscraper city"},
            {"narration": "Einstein discovered that gravity bends time itself.", "search": "einstein blackboard"},
            {"narration": "The closer you are to Earth's center, the slower your clock ticks.", "search": "planet earth space"},
            {"narration": "Scientists confirmed it with atomic clocks placed just a foot apart.", "search": "atomic clock"},
            {"narration": "The difference is tiny, but it is real, and GPS satellites must correct for it every day.", "search": "satellite orbit"},
            {"narration": "So if time bends this easily, what else are we wrong about? Tell me below.", "search": "dark galaxy"},
        ],
    }


def generate_content():
    print("-> Step 1: Generating viral script with Gemini...")
    keys = [os.environ.get("GEMINI_API_KEY", "")] + [
        os.environ.get(f"GEMINI_API_KEY_{i}", "") for i in range(2, 7)
    ]
    keys = [k.strip() for k in keys if k and k.strip()]
    models = [m.strip() for m in os.environ.get(
        "GEMINI_MODEL", "gemini-3.8-flash").split(",") if m.strip()]

    history = load_history()
    mode = os.environ.get("VIDEO_MODE", "story").lower()   # story | facts | mix
    if mode == "mix":
        mode = "story" if random.random() < 0.7 else "facts"
    if mode == "story":
        kind = "true" if random.random() < 0.7 else "fiction"
        cat = random.choice(STORY_TRUE if kind == "true" else STORY_FICTION)
        prompt = build_story_prompt(kind, cat, history, random.choice(FOCUS_SEEDS))
        print(f"-> Mode: STORY ({kind})")
    else:
        prompt = build_prompt(random.choice(CATEGORIES), history, random.choice(FOCUS_SEEDS))
        print("-> Mode: FACTS")

    for ki, key in enumerate(keys, 1):
        client = genai.Client(api_key=key)
        for model in models:
            for attempt in range(1, 5):
                try:
                    print(f"   key #{ki} / {model} / try {attempt}")
                    resp = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json", temperature=1.0),
                    )
                    data = parse_json(resp.text)
                    if not valid(data):
                        print("   invalid structure, retrying...")
                        continue
                    if too_similar(data["title"], history):
                        print("   topic too similar to an old one, retrying...")
                        continue
                    print("-> Script ready:", data["title"])
                    return data
                except Exception as e:
                    msg = str(e)
                    print(f"   error: {msg[:160]}")
                    if "404" in msg or "NOT_FOUND" in msg:
                        break  # wrong/retired model name, no point retrying
                    if "503" in msg or "UNAVAILABLE" in msg or "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        wait = 10 * attempt
                        print(f"   Gemini busy, waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        time.sleep(2)

    if os.environ.get("ALLOW_FALLBACK", "0") == "1":
        print("-> Gemini failed, using fallback script.")
        return get_fallback()
    raise Exception("Gemini could not produce a NEW topic. Stopping so no duplicate video is uploaded.")


# ----------------------------------------------------------------------------
# 2. Images (Pixabay) + cinematic grading
# ----------------------------------------------------------------------------
def fetch_image(query, out_path, used_ids):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key:
        return None
    words = (query or "").split()
    attempts = [
        (" ".join(words), "vertical"),
        (" ".join(words[:2]), "vertical"),
        (" ".join(words[:2]), "all"),
        (random.choice(GENERIC_QUERIES), "vertical"),
    ]
    for q, orient in attempts:
        if not q.strip():
            continue
        try:
            r = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": key, "q": q, "image_type": "photo",
                    "orientation": orient, "safesearch": "true",
                    "per_page": 20, "min_height": 1000,
                },
                timeout=20,
            )
            if r.status_code != 200:
                continue
            hits = [h for h in r.json().get("hits", []) if h["id"] not in used_ids]
            if not hits:
                continue
            hit = random.choice(hits[:10])
            url = hit.get("largeImageURL") or hit.get("webformatURL")
            img = requests.get(url, timeout=30)
            if img.status_code == 200 and len(img.content) > 5000:
                Path(out_path).write_bytes(img.content)
                used_ids.add(hit["id"])
                return str(out_path)
        except Exception as e:
            print(f"   pixabay notice: {str(e)[:120]}")
    return None


def gradient_image():
    top = np.array([12, 18, 40], dtype=np.float32)
    bot = np.array([2, 2, 8], dtype=np.float32)
    t = np.linspace(0, 1, BASE_H, dtype=np.float32)[:, None, None]
    arr = top * (1 - t) + bot * t
    arr = np.repeat(arr, BASE_W, axis=1)
    arr += np.random.normal(0, 3, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def prepare_image(path):
    """Cover-crop to oversized canvas, grade colors, add vignette."""
    try:
        img = Image.open(path).convert("RGB") if path else gradient_image()
    except Exception:
        img = gradient_image()

    scale = max(BASE_W / img.width, BASE_H / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1), Image.LANCZOS)
    left = (img.width - BASE_W) // 2
    top = (img.height - BASE_H) // 2
    img = img.crop((left, top, left + BASE_W, top + BASE_H))

    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = ImageEnhance.Brightness(img).enhance(0.88)

    arr = np.asarray(img).astype(np.float32)
    yy, xx = np.ogrid[:BASE_H, :BASE_W]
    d = np.sqrt(((xx - BASE_W / 2) / (BASE_W / 2)) ** 2 + ((yy - BASE_H / 2) / (BASE_H / 2)) ** 2)
    vignette = np.clip(1.08 - 0.42 * d ** 2, 0.25, 1.0)
    arr *= vignette[..., None]
    arr[..., 2] *= 1.05   # slight cold cinematic tint
    arr[..., 0] *= 0.98
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def kenburns_clip(base, duration, idx):
    """3D-feeling camera move: eased zoom + pan, with a quick dip at the cuts."""
    mode = idx % 4
    z0, z1 = (1.0, 1.3) if mode in (0, 2) else (1.3, 1.0)
    pan_x, pan_y = [(0, -1), (1, 0), (0, 1), (-1, 0)][mode]

    def frame(t):
        p = min(max(t / duration, 0), 1)
        p = p * p * (3 - 2 * p)  # ease in-out
        z = z0 + (z1 - z0) * p
        vw = BASE_W / z
        vh = vw * H / W
        mx, my = BASE_W - vw, BASE_H - vh
        ox = mx / 2 + pan_x * (mx / 2) * (2 * p - 1) * 0.9
        oy = my / 2 + pan_y * (my / 2) * (2 * p - 1) * 0.9
        box = (ox, oy, ox + vw, oy + vh)
        fr = np.asarray(base.resize((W, H), Image.BICUBIC, box=box))
        f = min(1.0, t / 0.12, max(duration - t, 0) / 0.12)
        if f < 1.0:
            fr = (fr * (0.15 + 0.85 * f)).astype(np.uint8)
        return fr

    return VideoClip(frame, duration=duration)


# ----------------------------------------------------------------------------
# 3. Voice
# ----------------------------------------------------------------------------
async def _edge_tts(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="+6%", pitch="-3Hz").save(path)


def make_voice(text, path):
    try:
        asyncio.run(_edge_tts(text, path))
        if os.path.getsize(path) > 1000:
            return
    except Exception as e:
        print(f"   edge-tts failed ({str(e)[:100]}), using gTTS")
    gTTS(text=text, lang="en", slow=False).save(path)


# ----------------------------------------------------------------------------
# 4. Music (generated, no downloads)
# ----------------------------------------------------------------------------
def make_music(path, duration, sr=44100):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.12 * t)
    sig = (
        0.50 * np.sin(2 * np.pi * 55.0 * t)
        + 0.35 * np.sin(2 * np.pi * 82.41 * t + lfo)
        + 0.25 * np.sin(2 * np.pi * 110.0 * t) * lfo
        + 0.12 * np.sin(2 * np.pi * 220.0 * t) * (1 - lfo)
    )
    beat = np.exp(-((t % 1.1) * 7.0))
    sig += 0.45 * np.sin(2 * np.pi * 48.0 * t) * beat
    fade = np.minimum(1.0, np.minimum(t / 1.5, (duration - t) / 1.5))
    sig *= fade
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * 0.8
    pcm = (sig * 32767).astype(np.int16)
    stereo = np.stack([pcm, pcm], axis=1).flatten()
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(stereo.tobytes())


# ----------------------------------------------------------------------------
# 5. Captions / hook overlays
# ----------------------------------------------------------------------------
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def load_font(size):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def chunk_words(text, max_words=3, max_chars=16):
    chunks, cur = [], []
    for w in text.split():
        if cur and (len(cur) >= max_words or len(" ".join(cur + [w])) > max_chars):
            chunks.append(" ".join(cur))
            cur = []
        cur.append(w)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def render_text_png(text, path, color, size=92, stroke=8, height=340, max_width=980):
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while size > 36:
        font = load_font(size)
        bbox = tmp.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if bbox[2] - bbox[0] <= max_width:
            break
        size -= 6
    img = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), text, font=font, stroke_width=stroke)
    x = (W - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (height - (bbox[3] - bbox[1])) // 2 - bbox[1]
    d.text((x, y), text, font=font, fill=color, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
    img.save(path)


def render_hook_png(text, path):
    font = load_font(74)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    size = 74
    while size > 40:
        font = load_font(size)
        bbox = tmp.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= 880:
            break
        size -= 4
    bbox = tmp.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    img = Image.new("RGBA", (W, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0 = (W - tw) // 2 - 45, (240 - th) // 2 - 40
    d.rounded_rectangle([x0, y0, x0 + tw + 90, y0 + th + 80], radius=26, fill=(255, 205, 0, 245))
    d.text(((W - tw) // 2 - bbox[0], (240 - th) // 2 - bbox[1]), text, font=font, fill=(10, 10, 10, 255))
    img.save(path)


# ----------------------------------------------------------------------------
# 6. Video assembly
# ----------------------------------------------------------------------------
def build_video(data, out_file="output.mp4"):
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir()

    scenes = data["scenes"]
    used_ids = set()
    visual_clips, voice_clips, caption_clips = [], [], []
    t = 0.0

    for i, sc in enumerate(scenes):
        narration = sc["narration"].strip()
        print(f"-> Scene {i + 1}/{len(scenes)}: {narration[:60]}...")

        apath = WORK / f"voice_{i}.mp3"
        make_voice(narration, str(apath))
        vc = AudioFileClip(str(apath))
        dur = vc.duration + 0.25

        img_path = fetch_image(sc.get("search", ""), WORK / f"img_{i}.jpg", used_ids)
        base = prepare_image(img_path)

        visual_clips.append(kenburns_clip(base, dur, i).with_start(t))
        voice_clips.append(vc.with_start(t + 0.05))

        # captions timed proportionally inside the spoken part
        chunks = chunk_words(narration)
        weights = [len(c) + 2 for c in chunks]
        total_w = sum(weights)
        cursor = t + 0.05
        for ci, chunk in enumerate(chunks):
            cdur = vc.duration * weights[ci] / total_w
            png = WORK / f"cap_{i}_{ci}.png"
            color = (255, 221, 0, 255) if ci % 2 else (255, 255, 255, 255)
            render_text_png(chunk.upper(), str(png), color)
            caption_clips.append(
                ImageClip(str(png)).with_start(cursor).with_duration(max(cdur, 0.3)).with_position(("center", 1150))
            )
            cursor += cdur

        if i == 0:
            hook = (data.get("hook_text") or "WAIT FOR IT").upper()
            hpng = WORK / "hook.png"
            render_hook_png(hook, str(hpng))
            caption_clips.append(
                ImageClip(str(hpng)).with_start(0).with_duration(min(3.0, dur)).with_position(("center", 250))
            )
        t += dur

    total = t + 0.3

    music_path = WORK / "music.wav"
    make_music(music_path, total)
    music = AudioFileClip(str(music_path))
    try:
        music = music.with_volume_scaled(0.16)
    except AttributeError:
        music = music.volumex(0.16)

    final_audio = CompositeAudioClip(voice_clips + [music])
    video = CompositeVideoClip(visual_clips + caption_clips, size=(W, H)).with_duration(total)
    video = video.with_audio(final_audio)

    print(f"-> Rendering {total:.1f}s video...")
    video.write_videofile(
        out_file,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="veryfast",
        threads=4,
        ffmpeg_params=["-crf", "21", "-pix_fmt", "yuv420p"],
        logger=None,
    )

    video.close()
    shutil.rmtree(WORK, ignore_errors=True)
    print("-> Video rendered!")
    return out_file


# ----------------------------------------------------------------------------
# 7. YouTube upload (SEO optimised)
# ----------------------------------------------------------------------------
def build_metadata(data):
    title = re.sub(r"#\w+", "", data["title"]).strip()[:88]
    if len(title) + 8 <= 100:
        title += " #Shorts"

    hashtags = ["Shorts"] + [re.sub(r"\W", "", h) for h in data.get("hashtags", []) if h]
    seen, tags_line = set(), []
    for h in hashtags:
        if h and h.lower() not in seen:
            seen.add(h.lower())
            tags_line.append("#" + h)
    tags_line = tags_line[:6]

    disclosure = ""
    if data.get("story_type") == "fiction":
        disclosure = "📖 This is an original fictional story made for entertainment.\n\n"
    description = (
        f"{data.get('description', '').strip()}\n\n"
        f"{disclosure}"
        "🔔 A new mind-blowing mystery every day - follow Mysterious AI so you never miss one.\n"
        "💬 Comment your theory below!\n\n"
        + " ".join(tags_line)
    )

    tags, total = [], 0
    for tag in ["shorts", "mysterious ai"] + data.get("tags", []):
        tag = str(tag).strip()[:60]
        if tag and total + len(tag) < 450:
            tags.append(tag)
            total += len(tag) + 1
    return title, description[:4900], tags


def upload_to_youtube(video_path, data):
    print("-> Connecting to YouTube API...")
    cid = os.environ.get("YOUTUBE_CLIENT_ID")
    secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN") or os.environ.get("YOUTUBE_REFRESH_TEKEN")
    if not all([cid, secret, refresh]):
        raise Exception("YouTube OAuth secrets are missing!")

    creds = Credentials(
        token=None, refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cid, client_secret=secret,
    )
    youtube = build("youtube", "v3", credentials=creds)

    title, description, tags = build_metadata(data)
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response, retries = None, 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise

    video_id = response.get("id")
    print(f"-> Uploaded! https://youtu.be/{video_id}")

    # First comment to boost engagement (needs the youtube.force-ssl scope; optional)
    comment = data.get("comment")
    if comment:
        try:
            youtube.commentThreads().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id,
                                  "topLevelComment": {"snippet": {"textOriginal": comment}}}},
            ).execute()
            print("-> First comment posted.")
        except Exception as e:
            print(f"-> Comment skipped: {str(e)[:150]}")
    return video_id


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Mysterious AI Cinematic Pipeline v2 ===")
    try:
        content = generate_content()
        video = build_video(content, "output.mp4")

        if DRY_RUN:
            print("=== DRY RUN: video created, upload skipped ===")
        else:
            upload_to_youtube(video, content)
            save_history(content["title"])
            os.remove(video)
            print("=== Video generated and uploaded successfully! ===")
    except Exception as e:
        print(f"Pipeline Critical Error: {e}")
        traceback.print_exc()
        raise
