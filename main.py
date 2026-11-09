import os
import time
import random
import requests
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS

# MoviePy modern imports
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.VideoClip import ImageClip, ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

def generate_viral_content():
    """Generates viral mystery and historical fact script using Gemini API with fallback backup script."""
    api_keys = []
    primary_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if primary_key:
        api_keys.append(primary_key)
        
    for i in range(2, 7):
        k = os.environ.get(f"GEMINI_API_KEY_{i}", "").strip()
        if k:
            api_keys.append(k)
            
    if not api_keys:
        return get_fallback_script()
    
    prompt = (
        "Create an extremely engaging, high-retention 30-second YouTube Short script about mind-blowing real-world facts, "
        "hidden historical truths, unsolved mysteries, or terrifying psychological facts. "
        "Draw inspiration from shocking facts like 'An entire town in Alaska living inside a single building (Begich Towers)' "
        "or 'The United States having no official national language at the federal level'. "
        "Start with a strong psychological hook or mind-bending question in the first 3 seconds.\n\n"
        "Format your output strictly as follows:\n"
        "TITLE: [Catchy viral title with emojis #shorts]\n"
        "DESCRIPTION: [Engaging description with #shorts #facts #mystery #history]\n"
        "SCRIPT: [The main narration text for voiceover]"
    )
    
    model_name = 'gemini-3.8-flash'
    
    for idx, api_key in enumerate(api_keys):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            
            if response and response.text:
                output = response.text.strip()
                title = "Mysterious AI Fact #shorts"
                description = "#shorts #mystery #facts"
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
                    
                return title, description, script
                
        except Exception as e:
            time.sleep(1)
                    
    return get_fallback_script()

def get_fallback_script():
    title = "The Town Where Everyone Lives in One Building 🏢❄️ #shorts"
    description = "Have you heard of Whittier, Alaska? An entire town lives under one roof. #shorts #history #facts"
    script = (
        "Did you know there is a town in Alaska where nearly the entire population lives inside a single multi-story building? "
        "Begich Towers contains a grocery store, post office, police station, and church all under one roof. "
        "Due to extreme weather, residents can go months without stepping outdoors. "
        "Even school children travel to class through a secret underground tunnel. "
        "Subscribe for more shocking real-world facts."
    )
    return title, description, script

def download_cinematic_video(output_filename="background.mp4"):
    """Downloads a real cinematic vertical background video using proper browser headers."""
    video_urls = [
        "https://videos.pexels.com/video-files/3195394/3195394-uhd_2160_3840_25fps.mp4",
        "https://videos.pexels.com/video-files/5377684/5377684-uhd_1080_1920_25fps.mp4",
        "https://videos.pexels.com/video-files/7578552/7578552-uhd_1080_1920_30fps.mp4"
    ]
    
    selected_url = random.choice(video_urls)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(selected_url, headers=headers, stream=True, timeout=15)
        if response.status_code == 200:
            with open(output_filename, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return output_filename
    except Exception as e:
        print(f"Download stream notice: {str(e)}")
        
    return None

def create_video_with_pro_thumbnail(script_text, video_title, output_filename="output.mp4"):
    """Creates a high-retention video featuring a professional documentary-style thumbnail and wrapped multi-line captions."""
    print("Generating voiceover audio...")
    if not script_text or not script_text.strip():
        raise Exception("No text to speak provided for video generation!")
        
    tts = gTTS(text=script_text, lang='en', slow=False)
    audio_path = "voiceover.mp3"
    tts.save(audio_path)
    
    audio_clip = AudioFileClip(audio_path)
    audio_duration = audio_clip.duration
    print(f"Audio duration required: {audio_duration:.2f} seconds")
    
    bg_video_path = download_cinematic_video()
    
    video_clip = None
    if bg_video_path and os.path.exists(bg_video_path):
        try:
            video_clip = VideoFileClip(bg_video_path)
            if video_clip.duration < audio_duration:
                from moviepy.video.compositing.concatenate import concatenate_videoclips
                loops = int(audio_duration // video_clip.duration) + 1
                video_clip = concatenate_videoclips([video_clip] * loops)
            video_clip = video_clip.subclipped(0, audio_duration)
        except Exception as e:
            print(f"Video clip load notice: {str(e)}")
            video_clip = None
            
    if video_clip is None:
        video_clip = ColorClip(size=(1080, 1920), color=(15, 12, 25), duration=audio_duration)
        
    clips_list = [video_clip]
    
    try:
        try:
            font_main = ImageFont.truetype("DejaVuSans-Bold.ttf", 68)
            font_sub = ImageFont.truetype("DejaVuSans-Bold.ttf", 46)
        except:
            font_main = ImageFont.load_default()
            font_sub = ImageFont.load_default()

        # 1. Professional High-CTR Thumbnail Title Card (Like your reference examples)
        hook_duration = min(4.0, audio_duration)
        img_thumb = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
        draw_t = ImageDraw.Draw(img_thumb)
        
        display_title = video_title.replace("#shorts", "").replace("!", "").strip().upper()
        
        # Draw striking yellow & red documentary style title banner similar to examples
        draw_t.rounded_rectangle([70, 720, 1010, 1180], radius=25, fill=(10, 10, 10, 230))
        draw_t.rectangle([70, 720, 1010, 830], fill=(240, 190, 20, 240)) # Yellow top banner
        draw_t.text((100, 740), "THE SHOCKING TRUTH", font=font_sub, fill=(10, 10, 10, 255))
        
        # Word wrapping for main title header
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

        # 2. Multi-line Wrapped Dynamic Captions (3-4 lines layout in lower third)
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
        print(f"Caption / Thumbnail warning: {str(e)}")

    final_composite = CompositeVideoClip(clips_list)
    
    try:
        final_composite = final_composite.with_audio(audio_clip)
    except AttributeError:
        final_composite = final_composite.set_audio(audio_clip)
        
    print(f"Rendering final professional video: {output_filename}...")
    final_composite.write_videofile(
        output_filename, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac',
        preset='ultrafast',
        ffmpeg_params=['-pix_fmt', 'yuv420p'],
        logger=None
    )
    
    audio_clip.close()
    video_clip.close()
    final_composite.close()
    
    if bg_video_path and os.path.exists(bg_video_path):
        os.remove(bg_video_path)
    if os.path.exists("pro_thumbnail.png"):
        os.remove("pro_thumbnail.png")
    for idx in range(100):
        p = f"caption_{idx}.png"
        if os.path.exists(p):
            os.remove(p)
            
    print("Video rendered successfully with professional thumbnail and captions!")
    return output_filename

def upload_to_youtube(video_file_path, title, description):
    """Uploads the rendered video to YouTube using OAuth2 credentials and Refresh Token."""
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
            "tags": ["shorts", "mystery", "facts", "ai", "mysteriousai"],
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    
    print(f"Uploading video file to YouTube: {video_file_path}...")
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
            
    print(f"Successfully uploaded! Video ID: {response.get('id')}")
    print(f"View it here: https://youtu.be/{response.get('id')}")

if __name__ == "__main__":
    print("=== Cinematic Mysterious AI Pipeline Initialized ===")
    
    try:
        title, description, script = generate_viral_content()
        print(f"[Generated Title]: {title}")
        
        video_path = create_video_with_pro_thumbnail(script, title, output_filename="output.mp4")
        
        if os.path.exists(video_path):
            upload_to_youtube(video_path, title, description)
            os.remove(video_path)
            print("=== Video Generated and Uploaded Successfully! ===")
        else:
            print(f"Error: Video file '{video_path}' was not created.")
            
    except Exception as e:
        print(f"Pipeline Error: {str(e)}")
