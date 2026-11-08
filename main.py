import os
import time
import random
import requests
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS

# MoviePy modern imports
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip

def generate_viral_content():
    """Generates viral mystery script using Gemini API with fallback backup script."""
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
        "Create an extremely engaging, high-retention 30-second YouTube Short script about an unsolved mystery, "
        "dark historical secret, or terrifying psychological fact. "
        "Start with a strong psychological hook in the first 3 seconds.\n\n"
        "Format your output strictly as follows:\n"
        "TITLE: [Catchy viral title with emojis #shorts]\n"
        "DESCRIPTION: [Engaging description with #shorts #mystery #facts]\n"
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
    title = "The Terrifying Glitch in Human Memory 🧠⚠️ #shorts"
    description = "Have you ever experienced the Mandela effect? Here is the terrifying truth about your brain. #shorts #mystery #facts"
    script = (
        "Did you know your brain is actively rewriting your memories every single day? "
        "Scientists discovered that every time you recall a memory, you aren't remembering the original event—you are remembering the last time you thought about it. "
        "This means a huge portion of what you believe happened in your past... never actually occurred the way you remember it. "
        "What else is your mind hiding from you? Subscribe for more dark psychological facts."
    )
    return title, description, script

def download_cinematic_video(output_filename="background.mp4"):
    """Selects from a curated list of high-end cinematic vertical videos without needing any API key."""
    
    # List of direct public cinematic vertical video URLs (Mystery, Dark, Abstract 3D, Moody atmosphere)
    cinematic_video_urls = [
        "https://videos.pexels.com/video-files/3195394/3195394-uhd_2160_3840_25fps.mp4",
        "https://videos.pexels.com/value/3195394/free-video-3195394.mp4?auto=compress&cs=tinysrgb&dpr=1&w=500",
        "https://videos.pexels.com/video-files/5377684/5377684-uhd_1080_1920_25fps.mp4",
        "https://videos.pexels.com/video-files/7578552/7578552-uhd_1080_1920_30fps.mp4",
        "https://videos.pexels.com/video-files/6981414/6981414-uhd_1080_1920_25fps.mp4"
    ]
    
    # Pick a random cinematic video link from the list
    selected_url = random.choice(cinematic_video_urls)
    
    print(f"Downloading cinematic background video from direct stream...")
    try:
        vid_data = requests.get(selected_url, stream=True, timeout=15)
        with open(output_filename, "wb") as f:
            for chunk in vid_data.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        print(f"Stream download error: {str(e)}, using absolute fallback...")
        # Absolute bulletproof backup link
        backup_url = "https://videos.pexels.com/video-files/5377684/5377684-uhd_1080_1920_25fps.mp4"
        vid_data = requests.get(backup_url, stream=True)
        with open(output_filename, "wb") as f:
            for chunk in vid_data.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
    print("Cinematic background video downloaded successfully!")
    return output_filename

def create_video(script_text, output_filename="output.mp4"):
    """Combines cinematic background video with gTTS voiceover audio."""
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
    
    print("Processing and trimming video with MoviePy...")
    video_clip = VideoFileClip(bg_video_path)
    
    if video_clip.duration < audio_duration:
        from moviepy.video.compositing.concatenate import concatenate_videoclips
        loops = int(audio_duration // video_clip.duration) + 1
        video_clip = concatenate_videoclips([video_clip] * loops)
        
    video_clip = video_clip.subclipped(0, audio_duration)
    
    try:
        final_video = video_clip.with_audio(audio_clip)
    except AttributeError:
        final_video = video_clip.set_audio(audio_clip)
    
    print(f"Rendering final cinematic video file: {output_filename}...")
    final_video.write_videofile(
        output_filename, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac',
        preset='ultrafast',
        ffmpeg_params=['-pix_fmt', 'yuv420p'],
        logger=None
    )
    
    audio_clip.close()
    final_video.close()
    video_clip.close()
    
    if os.path.exists(bg_video_path):
        os.remove(bg_video_path)
        
    print("Cinematic video rendering completed successfully!")
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
        
        video_path = create_video(script, output_filename="output.mp4")
        
        if os.path.exists(video_path):
            upload_to_youtube(video_path, title, description)
            os.remove(video_path)
            print("=== Cinematic Video Generated and Uploaded Successfully! ===")
        else:
            print(f"Error: Video file '{video_path}' was not created.")
            
    except Exception as e:
        print(f"Pipeline Error: {str(e)}")
