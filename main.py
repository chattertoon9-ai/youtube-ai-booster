import os
import time
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS

# MoviePy modern imports
from moviepy.video.VideoClip import ColorClip
from moviepy.audio.io.AudioFileClip import AudioFileClip

def generate_viral_content():
    """Generates viral mystery script using Gemini API with multiple keys rotation (Key 1 to 6)."""
    
    api_keys = []
    for i in range(1, 7):
        key_name = f"GEMINI_API_KEY_{i}" if i > 1 else "GEMINI_API_KEY"
        k = os.environ.get(key_name, "")
        if k.strip():
            api_keys.append(k.strip())
            
    if not api_keys:
        raw_keys = os.environ.get("GEMINI_API_KEY", "")
        api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        
    if not api_keys:
        raise Exception("No Gemini API keys found in environment variables!")
    
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
    
    for key_index, api_key in enumerate(api_keys):
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
                    script = output # Fallback to full text if parsing fails
                    
                return title, description, script
                
        except Exception as e:
            time.sleep(1)
                    
    raise Exception("All Gemini API keys failed or exhausted daily limits.")

def create_video(script_text, output_filename="output.mp4"):
    """Generates a reliable vertical video with proper YUV color formatting so YouTube displays the background correctly."""
    print("Generating voiceover audio...")
    if not script_text or not script_text.strip():
        raise Exception("No text to speak provided for video generation!")
        
    tts = gTTS(text=script_text, lang='en', slow=False)
    audio_path = "voiceover.mp3"
    tts.save(audio_path)
    
    audio_clip = AudioFileClip(audio_path)
    duration = audio_clip.duration
    print(f"Audio duration loaded: {duration:.2f} seconds")
    
    print(f"Creating vertical video background (1080x1920)...")
    bg_clip = ColorClip(size=(1080, 1920), color=(25, 35, 55), duration=duration)
    
    try:
        video = bg_clip.with_audio(audio_clip)
    except AttributeError:
        video = bg_clip.set_audio(audio_clip)
    
    print(f"Rendering final video file with yuv420p encoding: {output_filename}...")
    video.write_videofile(
        output_filename, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac',
        preset='ultrafast',
        pix_fmt='yuv420p',  # Required for YouTube and mobile players to show background color
        logger=None
    )
    
    audio_clip.close()
    video.close()
    bg_clip.close()
    
    print("Video rendering completed successfully!")
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
    print("=== Mysterious AI Multi-Video Pipeline Initialized ===")
    
    TOTAL_VIDEOS_TO_GENERATE = 4
    
    for i in range(1, TOTAL_VIDEOS_TO_GENERATE + 1):
        print(f"\n--- Starting Video {i} of {TOTAL_VIDEOS_TO_GENERATE} ---")
        try:
            title, description, script = generate_viral_content()
            print(f"[Generated Title]: {title}")
            
            output_filename = f"output_{i}.mp4"
            video_path = create_video(script, output_filename=output_filename)
            
            if os.path.exists(video_path):
                upload_to_youtube(video_path, title, description)
                os.remove(video_path)
            else:
                print(f"Error: Video file '{video_path}' was not created.")
                
            if i < TOTAL_VIDEOS_TO_GENERATE:
                print("Waiting 5 seconds before next video...")
                time.sleep(5)
                
        except Exception as e:
            print(f"Error in video #{i}: {str(e)}")
            continue

    print("\n=== All Videos Processed Successfully! ===")
