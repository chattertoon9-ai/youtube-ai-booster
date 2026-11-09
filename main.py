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
from moviepy.video.VideoClip import ColorClip
from moviepy.audio.io.AudioFileClip import AudioFileClip

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
    
    # Combined single powerful prompt covering both real-world historical facts and dark mysteries
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
        "Did you know there is a town in Alaska where nearly the entire population of over two hundred people lives inside a single multi-story building? "
        "Begich Towers contains a grocery store, post office, police station, and church all under one roof. "
        "Due to extreme weather and hurricane-force winds, residents can go months without ever stepping outside outdoors. "
        "Even school children travel to class through a secret underground tunnel. "
        "Would you be able to live your entire life inside one building? Subscribe for more shocking real-world facts."
    )
    return title, description, script

def create_video(script_text, output_filename="output.mp4"):
    """Generates a high-contrast visual video paired with gTTS voiceover audio safely without stream corruption errors."""
    print("Generating voiceover audio...")
    if not script_text or not script_text.strip():
        raise Exception("No text to speak provided for video generation!")
        
    tts = gTTS(text=script_text, lang='en', slow=False)
    audio_path = "voiceover.mp3"
    tts.save(audio_path)
    
    audio_clip = AudioFileClip(audio_path)
    audio_duration = audio_clip.duration
    print(f"Audio duration required: {audio_duration:.2f} seconds")
    
    print(f"Creating professional vertical cinematic background (1080x1920)...")
    # Using a sleek dark cinematic gradient/color theme (20, 25, 40) that renders reliably on YouTube Shorts
    video = ColorClip(size=(1080, 1920), color=(20, 25, 40), duration=audio_duration)
    
    try:
        final_video = video.with_audio(audio_clip)
    except AttributeError:
        final_video = video.set_audio(audio_clip)
    
    print(f"Rendering final video file with ffmpeg yuv420p params: {output_filename}...")
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
    video.close()
    
    print("Video rendering completed successfully without stream corruption!")
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
            print("=== Video Generated and Uploaded Successfully! ===")
        else:
            print(f"Error: Video file '{video_path}' was not created.")
            
    except Exception as e:
        print(f"Pipeline Error: {str(e)}")
