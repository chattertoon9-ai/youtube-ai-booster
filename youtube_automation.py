import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
import google.generativeai as genai
from gtts import gTTS
from moviepy.editor import AudioFileClip, ColorClip, TextClip, CompositeVideoClip

# 1. Gemini API Configure Karein (Script Generation ke liye)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def generate_viral_content():
    print("AI is generating a viral script...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = (
        "Write a short, highly engaging, viral YouTube Shorts script about an unknown psychological fact "
        "or mysterious AI secret. Keep it under 50 words, fast-paced, with a strong hook in the first 3 seconds. "
        "Also provide a catchy title starting with an emoji. Format: Title: [Title]\nScript: [Script]"
    )
    response = model.generate_content(prompt)
    text = response.text
    
    # Title aur Script ko alag karna
    lines = text.split('\n')
    title = "Mind Blowing AI & Psychology Facts 🔥 #Shorts"
    script = text
    
    for line in lines:
        if line.startswith("Title:"):
            title = line.replace("Title:", "").strip()
        elif line.startswith("Script:"):
            script = line.replace("Script:", "").strip()
            
    return title, script

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
    
    # 9:16 vertical video shorts ke liye (Solid background color ya custom background)
    bg_clip = ColorClip(size=(1080, 1920), color=(15, 15, 35), duration=duration)
    
    # Audio ko video ke sath sync karna
    video = bg_clip.set_audio(audio_clip)
    
    output_video = "final_video.mp4"
    video.write_videofile(output_video, fps=24, codec='libx264', audio_codec='aac')
    return output_video

def upload_to_youtube(video_path, title, description="Automated upload via AI & GitHub Actions"):
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
            'tags': ['shorts', 'viral', 'ai', 'facts'],
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
    # Step 1: AI se title aur script banayein
    title, script = generate_viral_content()
    print(f"Generated Title: {title}")
    print(f"Generated Script: {script}")
    
    # Step 2: Voiceover generate karein
    audio_file = create_voiceover(script)
    
    # Step 3: Video render karein
    video_file = create_video_file(audio_file)
    
    # Step 4: YouTube par upload kar dein
    upload_to_youtube(video_file, title=title)
