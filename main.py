import os
import time
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS

# MoviePy modern imports
from moviepy.video.VideoClip import ColorClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
try:
    from moviepy.video.tools.subtitles import TextClip
except ImportError:
    TextClip = None

def generate_viral_content():
    """Generates viral mystery script, title, and description using Gemini API with key rotation."""
    raw_keys = os.environ.get("GEMINI_API_KEY", "")
    api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
    
    if not api_keys:
        raise Exception("GEMINI_API_KEY environment variable is missing or empty.")
    
    prompt = (
        "Create an extremely engaging, high-retention 30-second YouTube Short script about an unsolved mystery, "
        "dark historical secret, or terrifying psychological fact. "
        "Start with a strong psychological hook in the first 3 seconds to keep viewers from scrolling away.\n\n"
        "Format your output strictly as follows:\n"
        "TITLE: [Catchy viral title with emojis #shorts]\n"
        "DESCRIPTION: [Engaging description with top 5 viral hashtags like #shorts #mystery #facts #scary #viral]\n"
        "SCRIPT: [The main narration text for voiceover]"
    )
    
    model_name = 'gemini-2.5-flash'
    
    for key_index, api_key in enumerate(api_keys):
        print(f"Attempting generation with API Key #{key_index + 1}...")
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            
            if response and response.text:
                print(f"Successfully generated content using API Key #{key_index + 1}")
                output = response.text.strip()
                
                title = "Mysterious AI Fact #shorts"
                description = "#shorts #mystery #facts"
                script = output
                
                lines = output.split('\n')
                for line in lines:
                    if line.startswith("TITLE:"):
                        title = line.replace("TITLE:", "").strip()
                    elif line.startswith("DESCRIPTION:"):
                        description = line.replace("DESCRIPTION:", "").strip()
                    elif line.startswith("SCRIPT:"):
                        script = line.replace("SCRIPT:", "").strip()
                        
                return title, description, script
                
        except Exception as e:
            print(f"API Key #{key_index + 1} failed: {str(e)}")
            time.sleep(2)
                    
    raise Exception("All API keys failed or exhausted daily limits.")

def create_video(script_text, output_filename="output.mp4"):
    """Converts script text to speech and generates a dark vertical background video using MoviePy."""
    print("Generating voiceover audio...")
    tts = gTTS(text=script_text, lang='en', slow=False)
    audio_path = "voiceover.mp3"
    tts.save(audio_path)
    
    # Load audio to get duration
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    print(f"Creating vertical video (Duration: {duration:.2f}s)...")
    # Create a dark background for mysterious look (1080x1920 vertical format for Shorts)
    bg_clip = ColorClip(size=(1080, 1920), color=(15, 15, 20), duration=duration)
    
    video = bg_clip
    
    # Add text overlay if TextClip is available and working
    if TextClip is not None:
        try:
            txt_clip = TextClip(
                script_text[:120] + "...", 
                fontsize=50, 
                color='white', 
                size=(900, None), 
                method='caption'
            ).set_duration(duration).set_position('center')
            
            video = CompositeVideoClip([bg_clip, txt_clip])
        except Exception as e:
            print(f"TextClip warning (proceeding with background only): {e}")
            
    video = video.set_audio(audio_clip)
    
    print(f"Rendering video file: {output_filename}...")
    video.write_videofile(
        output_filename, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac',
        preset='ultrafast',
        logger=None
    )
    print("Video rendering completed successfully!")
    return output_filename

def upload_to_youtube(video_file_path, title, description):
    """Uploads the rendered video to YouTube using OAuth2 credentials and Refresh Token."""
    client_id = os.environ.get("YOUTUBE_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    
    if not all([client_id, client_secret, refresh_token]):
        raise Exception("YouTube OAuth secrets are missing in environment variables!")
        
    print("Authenticating with YouTube API...")
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
            print(f"Upload progress: {int(status.progress() * 100)}%")
            
    print(f"Successfully uploaded! Video ID: {response.get('id')}")
    print(f"View it here: https://youtu.be/{response.get('id')}")

if __name__ == "__main__":
    print("=== Mysterious AI Pipeline Initialized ===")
    
    # 1. Generate Title, Description & Script via Gemini
    title, description, script = generate_viral_content()
    print(f"\n[Generated Title]: {title}")
    print(f"[Generated Description]: {description}")
    
    # 2. Render Video (Audio + Visuals)
    video_path = create_video(script)
    
    # 3. Upload to YouTube
    if os.path.exists(video_path):
        upload_to_youtube(video_path, title, description)
    else:
        print(f"Error: Video file '{video_path}' was not created.")
