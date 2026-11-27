"""
Mysterious AI - YouTube Shorts auto pipeline (Pro Level)

Flow:
1. content_generator.generate_content() -> topic/title/script/description/tags
2. Voiceover (edge-tts, fallback gTTS)
3. Visuals   (Pixabay vertical/high-res photos, fallback atmospheric dark gradients)
4. Video     (MoviePy 720x1280, Ken Burns zoom + subtle pan, vignette + crisp captions)
5. Upload    (YouTube Data API v3, comments enabled, not made for kids)
6. mark_topic_used() after successful upload
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
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

BASE_DIR = Path(__file__).resolve().parent
for candidate in (BASE_DIR, BASE_DIR.parent, BASE_DIR / "src", BASE_DIR / "app"):
    if candidate.exists():
        c_str = str(candidate)
        if c_str not in sys.path:
            sys.path.insert(0, c_str)

from content_generator import QuotaExhausted, generate_content, mark_topic_used

W, H = 720, 1280
FPS = 24
SECONDS_PER_IMAGE = 4.2
WORDS_PER_CAPTION = 4
OUT_DIR = str(BASE_DIR / "output")
TTS_VOICE = os.environ.get("TTS_VOICE", "en-US-AndrewNeural")
DRY_RUN = os.environ.get("DRY_RUN", "").strip() in ("1", "true", "True", "yes")

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def _get_yt_env(*candidates: str) -> str:
    for name in candidates:
        val = os.environ.get(name, "").strip()
        if val:
            return val
    upper_targets = {c.upper() for c in candidates}
    for env_key, env_val in os.environ.items():
        if env_key.upper() in upper_targets:
            cleaned = str(env_val).strip()
            if cleaned:
                return cleaned
    return ""


# ---------------- VOICE ----------------
async def _edge_tts(text, path):
    import edge_tts

    communicate = edge_tts.Communicate(text, TTS_VOICE, rate="+4%", pitch="-2Hz")
    await asyncio.wait_for(communicate.save(path), timeout=90)


def make_voice(text, path):
    try:
        asyncio.run(_edge_tts(text, path))
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            print(f"[OK] Voice: edge-tts ({TTS_VOICE})")
            return path
    except Exception as e:
        print(f"[WARN] edge-tts fail ({str(e)[:120]}), trying gTTS...")

    from gtts import gTTS

    gTTS(text=text, lang="en", tld="com").save(path)
    print("[OK] Voice: gTTS")
    return path


# ---------------- IMAGES ----------------
def _build_vignette_mask(w, h):
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    nx = (x - cx) / (w * 0.55)
    ny = (y - cy) / (h * 0.55)
    dist = np.sqrt(nx * nx + ny * ny)
    vignette = np.clip(1.0 - 0.45 * (dist ** 1.6), 0.35, 1.0)
    return vignette.reshape(h, w, 1)


VIGNETTE_ARR = _build_vignette_mask(W, H)


def _cover(img, w, h):
    r = max(w / img.width, h / img.height)
    nw, nh = int(img.width * r) + 2, int(img.height * r) + 2
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    img = img.crop((left, top, left + w, top + h))
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Brightness(img).enhance(0.62)
    arr = np.asarray(img, dtype=np.float32) * VIGNETTE_ARR
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB")


def _gradient(w, h):
    palettes = [
        ((10, 14, 28), (48, 18, 56)),
        ((8, 22, 32), (24, 58, 68)),
        ((24, 12, 18), (68, 24, 28)),
        ((12, 16, 24), (36, 44, 66)),
    ]
    c1_rgb, c2_rgb = random.choice(palettes)
    c1 = np.array(c1_rgb, dtype=np.float32)
    c2 = np.array(c2_rgb, dtype=np.float32)
    t = np.linspace(0, 1, h).reshape(h, 1, 1)
    arr = (c1 * (1.0 - t) + c2 * t) * np.ones((h, w, 1), dtype=np.float32)
    arr = np.clip(arr * VIGNETTE_ARR, 0, 255).astype("uint8")
    return Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(radius=2))


def fetch_images(queries, need):
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    urls = []
    if key:
        for q in queries:
            if len(urls) >= need * 2:
                break
            try:
                r = requests.get(
                    "https://pixabay.com/api/",
                    params={
                        "key": key,
                        "q": str(q)[:100],
                        "image_type": "photo",
                        "orientation": "vertical",
                        "min_height": 900,
                        "safesearch": "true",
                        "per_page": 20,
                    },
                    timeout=20,
                )
                r.raise_for_status()
                hits = r.json().get("hits", [])
                random.shuffle(hits)
                for h in hits:
                    u = h.get("largeImageURL") or h.get("webformatURL")
                    if u and u not in urls:
                        urls.append(u)
            except Exception as e:
                print(f"[WARN] Pixabay '{q}' fail: {str(e)[:110]}")
    else:
        print("[WARN] PIXABAY_API_KEY not set, using atmospheric gradient backgrounds.")

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
            print(f"[WARN] Image download fail: {str(e)[:110]}")

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
    """Split script into punchy 4-word chunks timed proportionally to voice duration."""
    words = script.split()
    chunks = [
        " ".join(words[i : i + WORDS_PER_CAPTION])
        for i in range(0, len(words), WORDS_PER_CAPTION)
    ]
    weights = [max(len(c), 1) for c in chunks]
    total = float(sum(weights))
    font = _font(58)
    caps, t = [], 0.0

    for chunk, wgt in zip(chunks, weights):
        dur = duration * wgt / total
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        wrapped = "\n".join(textwrap.wrap(chunk, width=16))

        # Soft dark backing pill behind caption for high contrast
        bbox = d.multiline_textbbox(
            (W // 2, int(H * 0.62)),
            wrapped,
            font=font,
            anchor="ma",
            align="center",
            spacing=12,
            stroke_width=6,
        )
        pad_x, pad_y = 28, 16
        d.rounded_rectangle(
            (
                max(24, bbox[0] - pad_x),
                max(24, bbox[1] - pad_y),
                min(W - 24, bbox[2] + pad_x),
                min(H - 24, bbox[3] + pad_y),
            ),
            radius=22,
            fill=(0, 0, 0, 130),
        )

        d.multiline_text(
            (W // 2, int(H * 0.62)),
            wrapped,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=6,
            stroke_fill=(0, 0, 0, 255),
            anchor="ma",
            align="center",
            spacing=12,
        )
        caps.append((t, t + dur, overlay))
        t += dur
    return caps


# ---------------- VIDEO ----------------
def render_video(content, audio_path, out_path):
    from moviepy.editor import AudioFileClip, VideoClip

    audio = AudioFileClip(audio_path)
    duration = audio.duration + 0.6

    n_img = max(1, math.ceil(duration / SECONDS_PER_IMAGE))
    queries = [str(t) for t in content["tags"][:3]] + [
        content["topic"],
        "dark mystery",
        "night fog",
    ]
    images = fetch_images(queries, n_img)
    seg = duration / n_img
    captions = build_captions(content["script"], audio.duration)

    def make_frame(t):
        i = min(int(t / seg), n_img - 1)
        p = max(0.0, min(1.0, (t - i * seg) / seg))
        scale = 1.04 + 0.08 * p
        cw, ch = W / scale, H / scale
        drift_x = ((i % 2) * 2 - 1) * (p - 0.5) * 24.0
        drift_y = (-1 if i % 3 == 0 else 1) * (p - 0.5) * 20.0
        x0 = max(0.0, min(W - cw, (W - cw) / 2.0 + drift_x))
        y0 = max(0.0, min(H - ch, (H - ch) / 2.0 + drift_y))

        frame = images[i].resize(
            (W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch)
        ).convert("RGBA")

        for start, end, overlay in captions:
            if start <= t < end:
                frame = Image.alpha_composite(frame, overlay)
                break
        return np.asarray(frame.convert("RGB"))

    clip = VideoClip(make_frame, duration=duration).set_audio(audio)
    try:
        clip.write_videofile(
            out_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            preset="ultrafast",
            threads=2,
            ffmpeg_params=["-pix_fmt", "yuv420p"],
            logger=None,
        )
    finally:
        clip.close()
        audio.close()
    print(f"[OK] Video ready: {out_path} ({duration:.1f}s)")
    return out_path


# ---------------- YOUTUBE UPLOAD ----------------
def upload_video(path, content):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    refresh_token = _get_yt_env(
        "YT_REFRESH_TOKEN", "YOUTUBE_REFRESH_TOKEN", "Youtube_REFRESH_TOKEN"
    )
    client_id = _get_yt_env(
        "YT_CLIENT_ID", "YOUTUBE_CLIENT_ID", "Youtube_CLIENT_ID"
    )
    client_secret = _get_yt_env(
        "YT_CLIENT_SECRET",
        "YOUTUBE_CLIENT_SECRET",
        "YOUTUBE_cLIENT_SECRET",
        "Youtube_CLIENT_SECRET",
    )

    if not all([refresh_token, client_id, client_secret]):
        raise RuntimeError(
            "Missing YouTube OAuth credentials. Verify YT_* or YOUTUBE_* secrets in GitHub Actions."
        )

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    title = re.sub(r"[<>]", "", content["title"]).strip()[:100]
    tags = []
    total = 0
    for t in content["tags"]:
        t = re.sub(r"[<>]", "", str(t)).strip()
        if t and total + len(t) < 450:
            tags.append(t)
            total += len(t) + 1

    body = {
        "snippet": {
            "title": title,
            "description": content["description"][:4900],
            "tags": tags,
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        path, mimetype="video/mp4", chunksize=4 * 1024 * 1024, resumable=True
    )
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response, retries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"[UPLOAD] {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                wait = 2 ** retries
                print(f"[UPLOAD] server error {e.resp.status}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
        except (ConnectionError, TimeoutError) as e:
            if retries < 5:
                retries += 1
                print(f"[UPLOAD] network error ({e}), retry {retries}/5...")
                time.sleep(2 ** retries)
                continue
            raise

    video_id = response["id"]
    print(f"[OK] Uploaded: https://youtube.com/shorts/{video_id}")
    return video_id


# ---------------- MAIN ----------------
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    try:
        content = generate_content(save=False)
    except QuotaExhausted as e:
        print(f"[FATAL] {e}")
        sys.exit(1)
    print(f"[STEP 1/4] Content ready: {content['title']}")

    audio_path = make_voice(content["script"], os.path.join(OUT_DIR, "voice.mp3"))
    print("[STEP 2/4] Voice ready")

    video_path = render_video(content, audio_path, os.path.join(OUT_DIR, "short.mp4"))
    print("[STEP 3/4] Video ready")

    if DRY_RUN:
        print("[DRY_RUN] Upload skipped.")
        return

    upload_video(video_path, content)
    mark_topic_used(content["topic"])
    print("[STEP 4/4] Upload done, topic history updated")


if __name__ == "__main__":
    main()
