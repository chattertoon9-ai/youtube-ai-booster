import os
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google import genai
from gtts import gTTS
from moviepy.editor import AudioFileClip, ColorClip

# 1. New Google GenAI Client Configure Karein
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def generate_viral_content():
    print("AI is generating a viral script...")
    prompt = (
        "Write a short, highly engaging, viral YouTube Shorts script about an unknown psychological fact "
        "or mysterious AI secret. Keep it under 50 words, fast-paced, with a strong hook in the first 3 seconds. "
        "Also provide a catchy title starting with an emoji. Format: Title: [Title]\nScript: [Script]"
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Naye client ka tareeqa script generate karne ke liye
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
            )
            text = response.text
            
            title = "Mind Blowing AI & Psychology Facts 🔥 #Shorts"
            script = text
            
            lines = text.split('\n')
            for line in lines:
                if line.startswith("Title:"):
                    title = line.replace("Title:", "").strip()
                elif line.startswith("Script:"):
                    script = line.replace("Script:", "").strip()
                    
            return title, script
        except Exception as e:
            print(f"Error encountered: {e}. Retrying in 30 seconds (Attempt {attempt+1}/{max_retries})...")
            time.sleep(30)
            
    raise Exception("Failed to generate content after multiple retries.")

def create_voiceover(script):
    print("Converting script to voiceover...")
    tts = gTTS(text=script, lang='en', slow=False)
    audio_path = "voice.mp3"
    tts.save(audio_path)
    return audio_path

def create_video_file(audio_path):
    print("Rendering video...")
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    
    bg_clip = ColorClip(size=(1080, 1920), color=(15, 15, 35), duration=duration)
    video = bg_clip.set_audio(audio_clip)
    
    output_video = "final_video.mp4"
    video.write_videofile(output_video, fps=24, codec='libx264', audio_codec='aac')
    return output_video

def upload_to_youtube(video_path, title, description="Automated upload via AI Vault & GitHub Actions"):
    print("Uploading video to YouTube...")
    
    creds = Credentials(
        token=os.environ.get("YOUTUBE_ACCESS_TOKEN"),
        refresh_token=os.environ.get("YOUTUBE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("YOUTUBE_CLIENT_ID"),
        client_secret=os.environ.get("YOUTUBE_CLIENT_SECRET")
    )
    
    youtube = build('youtube', 'v3', credentials=creds)

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['shorts', 'viral', 'ai', 'facts', 'aivault'],
            'categoryId': '22'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    print(f"Video uploaded successfully! Video ID: {response.get('id')}")

if __name__ == "__main__":
    title, script = generate_viral_content()
    print(f"Generated Title: {title}")
    print(f"Generated Script: {script}")
    
    audio_file = create_voiceover(script)
    video_file = create_video_file(audio_file)
    upload_to_youtube(video_file, title=title)
