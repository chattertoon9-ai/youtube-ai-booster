import os
import time
import random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS

# MoviePy modern imports
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.video.VideoClip import ImageClip, ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

def generate_viral_content():
    """Generates viral mystery and historical fact script using Gemini API with fallback backup script."""
    print("-> Step 1: Initializing Gemini API keys...")
    api_keys = []
    primary_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if primary_key:
        api_keys.append(primary_key)
        
    for i in range(2, 7):
        k = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            api_keys.append(k)
            
    if not api_keys:
        print("-> No Gemini API keys found. Using fallback script.")
        return get_fallback_script()
    
    prompt = (
        "Create an extremely engaging, high-retention 30-second YouTube Short script about a completely unique, mind-blowing real-world fact, "
        "hidden historical truth, unsolved mystery, or terrifying psychological fact. Do NOT repeat previous topics. "
        "Start with a strong psychological hook or mind-bending question in the first 3 seconds.\n\n"
        "Format your output strictly as follows:\n"
        "TITLE: [Catchy viral title with emojis #shorts]\n"
        "DESCRIPTION: [Engaging description optimized for viral reach, loaded with #shorts #facts #mystery #history #viral]\n"
        "SCRIPT: [The main narration text for voiceover]"
    )
    
    model_name = 'gemini-3.8-flash'
    
    for idx, api_key in enumerate(api_keys):
        try:
            print(f"-> Attempting Gemini generation with Key index {idx+1}...")
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            
            if response and response.text:
                output = response.text.strip()
                title = "Mysterious AI Fact #shorts"
                description = "#shorts #mystery #facts #viral"
                script = output
                
                lines = output.split('\n')
                script_lines = []
                capture_script = False
                
                for line in lines:
                    if line.startswith("TITLE:"):
                        title = line.replace("TITLE:", "").strip()
                    elif line.startswith("DESCRIPTION:"):
                        description = line.replace("DESCRIPTION:", "").strip()
                    elif line.startswith("SCRIPT:"):
                        capture_script = True
                        script_lines.append(line.replace("SCRIPT:", "").strip())
                    elif capture_script:
                        script_lines.append(line.strip())
                
                if script_lines and "".join(script_lines).strip():
                    script = " ".join(script_lines)
                elif not script or len(script) < 10:
                    script = output
                    
                print("-> Gemini script generated successfully!")
                return title, description, script
                
        except Exception as e:
            print(f"-> Gemini API key {idx+1} error: {str(e)}")
            time.sleep(1)
                    
    print("-> All Gemini keys failed. Using fallback script.")
    return get_fallback_script()

def get_fallback_script():
    """Returns a random unique script from a diverse pool to prevent duplication."""
    fallback_topics = [
        (
            "The Country With No Official Language 🇺🇸🤫 #shorts",
            "Did you know the United States has no official national language? #shorts #facts #history #viral",
            "Did you know that the United States does not actually have an official language at the federal level? "
            "Despite English being widely spoken and used in government, the US Constitution and federal laws "
            "have never declared any official national language. Individual states can choose their own, "
            "but the entire country has no official tongue. "
            "Subscribe for more mind-blowing historical secrets."
        ),
        (
            "The Terrifying Glitch in Human Memory 🧠⚠️ #shorts",
            "Have you ever experienced the Mandela effect? Here is the truth about your brain. #shorts #mystery #facts #viral",
            "Did you know your brain is actively rewriting your memories every single day? "
            "Scientists discovered that every time you recall a memory, you aren't remembering the original event—you are remembering the last time you thought about it. "
            "This means a huge portion of what you believe happened in your past never actually occurred the way you remember it. "
            "Subscribe for more dark psychological facts."
        ),
        (
            "The Secret Deep Sea Anomaly Nobody Talks About 🌊⚓ #shorts",
            "What is hiding at the bottom of the ocean? #shorts #mystery #ocean #viral",
            "Did you know we know less about the deep ocean floor than we do about the surface of Mars? "
            "More than eighty percent of our oceans remain completely unmapped and unexplored. "
            "Deep beneath the crushing pressure, scientists frequently pick up unexplained acoustic anomalies and mysterious sounds "
            "that modern science still cannot identify. What secrets are lurking in the dark abyss? "
            "Subscribe for more unsolved mysteries."
        )
    ]
    return random.choice(fallback_topics)

def download_pixabay_image(query_keyword="mystery history dark cinematic", output_filename="bg_reference.jpg"):
    """Fetches high-vibrant professional photo background from Pixabay API with enhanced clarity and brightness."""
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "58493789-48e94ff1d6193dbd5fce48fc5").strip()
    
    search_queries = [
        "vibrant cinematic mystery 4k", 
        "dramatic historical architecture 4k", 
        "epic dark fantasy background", 
        "stunning cinematic vintage secret"
    ]
    selected_query = random.choice(search_queries)
    
    api_url = f"https://pixabay.com/api/?key={pixabay_key}&q={requests.utils.quote(selected_query)}&image_type=photo&orientation=vertical&safesearch=true&per_page=15"
    
    try:
        print(f"-> Searching Pixabay for vibrant image: '{selected_query}'...")
        res = requests.get(api_url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            hits = data.get("hits", [])
            if hits:
                img_item = random.choice(hits)
                img_url = img_item.get("largeImageURL") or img_item.get("webformatURL")
                if img_url:
                    img_res = requests.get(img_url, timeout=15)
                    if img_res.status_code == 200:
                        with open(output_filename, "wb") as f:
                            f.write(img_res.content)
                        
                        img = Image.open(output_filename).convert("RGBA")
                        img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
                        
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(1.25)
                        
                        overlay = Image.new("RGBA", img.size, (10, 10, 20, 80))
                        img = Image.alpha_composite(img, overlay)
                        img.convert("RGB").save(output_filename)
                        print("-> Pixabay background image downloaded and enhanced successfully!")
                        return output_filename
    except Exception as e:
        print(f"-> Pixabay API notice: {str(e)}")
        
    return None

def download_background_music(output_filename="bg_music.mp3"):
    """Downloads a royalty-free suspenseful background music track."""
    music_urls = [
        "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf756.mp3?filename=cinematic-time-suspense-115990.mp3",
        "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c365825d.mp3?filename=mystery-brand-110846.mp3"
    ]
    selected_url = random.choice(music_urls)
    try:
        print("-> Downloading background suspense music...")
        res = requests.get(selected_url, timeout=15)
        if res.status_code == 200:
            with open(output_filename, "wb") as f:
                f.write(res.content)
            print("-> Background music downloaded successfully!")
            return output_filename
    except Exception as e:
        print(f"-> Background music download notice: {str(e)}")
    return None

def create_video_with_pixabay_visuals(script_text, video_title, output_filename="output.mp4"):
    """Creates a high-retention video featuring Pixabay vibrant photos, background music, pro thumbnail, and wrapped captions."""
    print("-> Generating voiceover audio with gTTS...")
    if not script_text or not script_text.strip():
        raise Exception("No text to speak provided for video generation!")
        
    tts = gTTS(text=script_text, lang='en', slow=False)
    audio_path = "voiceover.mp3"
    tts.save(audio_path)
    
    voice_clip = AudioFileClip(audio_path)
    audio_duration = voice_clip.duration
    print(f"-> Audio duration required: {audio_duration:.2f} seconds")
    
    music_path = download_background_music()
    audio_final = voice_clip
    
    if music_path and os.path.exists(music_path):
        try:
            music_clip = AudioFileClip(music_path)
            if music_clip.duration < audio_duration:
                loops = int(audio_duration // music_clip.duration) + 1
                from moviepy.audio.AudioClip import concatenate_audioclips
                music_clip = concatenate_audioclips([music_clip] * loops)
            music_clip = music_clip.subclipped(0, audio_duration)
            
            try:
                music_clip = music_clip.with_volume_scaled(0.12)
            except AttributeError:
                music_clip = music_clip.volumex(0.12)
                
            audio_final = CompositeAudioClip([voice_clip, music_clip])
            print("-> Background music successfully mixed with voiceover!")
        except Exception as e:
            print(f"-> Audio mixing notice: {str(e)}")

    bg_image_path = download_pixabay_image()
    
    bg_clip = None
    if bg_image_path and os.path.exists(bg_image_path):
        try:
            bg_clip = ImageClip(bg_image_path).with_duration(audio_duration)
        except Exception as e:
            print(f"-> Background image clip load notice: {str(e)}")
            bg_clip = None
            
    if bg_clip is None:
        bg_clip = ColorClip(size=(1080, 1920), color=(15, 12, 25), duration=audio_duration)
        
    clips_list = [bg_clip]
    
    try:
        try:
            font_main = ImageFont.truetype("DejaVuSans-Bold.ttf", 68)
            font_sub = ImageFont.truetype("DejaVuSans-Bold.ttf", 46)
        except:
            font_main = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        # 1. Professional High-CTR Thumbnail Title Card (First 4 seconds)
        hook_duration = min(4.0, audio_duration)
        img_thumb = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        draw_t = ImageDraw.Draw(img_thumb)
        
        display_title = video_title.replace("#shorts", "").replace("!", "").strip().upper()
        
        draw_t.rounded_rectangle([70, 720, 1010, 1180], radius=25, fill=(10, 10, 10, 230))
        draw_t.rectangle([70, 720, 1010, 830], fill=(240, 190, 20, 240))
        draw_t.text((100, 740), "THE SHOCKING TRUTH", font=font_sub, fill=(10, 10, 10, 255))
        
        words_t = display_title.split()
        lines_t = []
        cur_l = []
        for w in words_t:
            cur_l.append(w)
            test_s = " ".join(cur_l)
            bbox = draw_t.textbbox((0, 0), test_s, font=font_main)
            if (bbox[2] - bbox[0]) > 860:
                cur_l.pop()
                lines_t.append(" ".join(cur_l))
                cur_l = [w]
        if cur_l:
            lines_t.append(" ".join(cur_l))
            
        y_t = 880
        for lt in lines_t[:3]:
            draw_t.text((100, y_t), lt, font=font_main, fill=(255, 255, 255, 255))
            y_t += 75
            
        thumb_path = "pro_thumbnail.png"
        img_thumb.save(thumb_path)
        clips_list.append(ImageClip(thumb_path).with_duration(hook_duration).with_start(0))

        # 2. Multi-line Wrapped Dynamic Captions
        words = script_text.split()
        chunk_size = 10
        chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
        
        remaining_duration = max(audio_duration - hook_duration, 1.0)
        chunk_duration = remaining_duration / max(len(chunks), 1)
        
        for idx, chunk in enumerate(chunks):
            start_t = hook_duration + (idx * chunk_duration)
            end_t = min(start_t + chunk_duration, audio_duration)
            dur = max(end_t - start_t, 1.0)
            
            img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            words_c = chunk.split()
            wrapped_lines = []
            current_line = []
            
            for word in words_c:
                current_line.append(word)
                test_line = " ".join(current_line)
                bbox = draw.textbbox((0, 0), test_line, font=font_sub)
                if (bbox[2] - bbox[0]) > 860:
                    current_line.pop()
                    wrapped_lines.append(" ".join(current_line))
                    current_line = [word]
            if current_line:
                wrapped_lines.append(" ".join(current_line))
                
            box_height = len(wrapped_lines) * 60 + 40
            box_y = 1250
            draw.rounded_rectangle([80, box_y, 1000, box_y + box_height], radius=20, fill=(0, 0, 0, 220))
            
            line_y = box_y + 20
            for line_text in wrapped_lines:
                bbox_l = draw.textbbox((0, 0), line_text, font=font_sub)
                lw = bbox_l[2] - bbox_l[0]
                lx = (1080 - lw) / 2
                draw.text((lx, line_y), line_text, font=font_sub, fill=(255, 255, 0, 255))
                line_y += 55
                
            img_path = f"caption_{idx}.png"
            img.save(img_path)
            clips_list.append(ImageClip(img_path).with_duration(dur).with_start(start_t))

    except Exception as e:
        print(f"-> Caption / Thumbnail rendering warning: {str(e)}")

    final_composite = CompositeVideoClip(clips_list)
    
    try:
        final_composite = final_composite.with_audio(audio_final)
    except AttributeError:
        final_composite = final_composite.set_audio(audio_final)
        
    print(f"-> Rendering final professional video: {output_filename}...")
    final_composite.write_videofile(
        output_filename, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac',
        preset='ultrafast',
        ffmpeg_params=['-pix_fmt', 'yuv420p'],
        logger=None
    )
    
    voice_clip.close()
    bg_clip.close()
    final_composite.close()
    
    if bg_image_path and os.path.exists(bg_image_path):
        os.remove(bg_image_path)
    if music_path and os.path.exists(music_path):
        os.remove(music_path)
    if os.path.exists("pro_thumbnail.png"):
        os.remove("pro_thumbnail.png")
    for idx in range(100):
        p = f"caption_{idx}.png"
        if os.path.exists(p):
            os.remove(p)
            
    print("-> Video rendered successfully!")
    return output_filename

def upload_to_youtube(video_file_path, title, description):
    """Uploads the rendered video to YouTube using OAuth2 credentials and Refresh Token."""
    print("-> Connecting to YouTube API...")
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TEKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise Exception("YouTube OAuth secrets are missing in environment variables!")
        
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    
    youtube = build("youtube", "v3", credentials=credentials)
    
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": ["shorts", "mystery", "facts", "ai", "mysteriousai", "viral"],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    print(f"-> Uploading video file to YouTube: {video_file_path}...")
    media = MediaFileUpload(video_file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pass
            
    print(f"-> Successfully uploaded! Video ID: {response.get('id')}")
    print(f"-> View it here: https://youtu.be/{response.get('id')}")

if __name__ == "__main__":
    print("=== Cinematic Mysterious AI Pipeline Initialized ===")
    
    try:
        title, description, script = generate_viral_content()
        print(f"[Generated Title]: {title}")
        
        video_path = create_video_with_pixabay_visuals(script, title, output_filename="output.mp4")
        
        if video_path and os.path.exists(video_path):
            upload_to_youtube(video_path, title, description)
            os.remove(video_path)
            print("=== Video Generated and Uploaded Successfully! ===")
        else:
            print(f"Error: Video file was not created properly.")
            
    except Exception as e:
        import traceback
        print(f"Pipeline Critical Error: {str(e)}")
        traceback.print_exc()
        raise e
