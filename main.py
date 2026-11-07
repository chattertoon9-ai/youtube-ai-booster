import os
import time
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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
            "title": title[:100],  # YouTube allows max 100 characters for title
            "description": description,
            "tags": ["shorts", "mystery", "facts", "ai", "mysteriousai"],
            "categoryId": "24"  # Entertainment category
        },
        "status": {
            "privacyStatus": "public",  # Set to 'private' if you want to test first
            "selfDeclaredMadeForKids": False
        }
    }
    
    print(f"Uploading video file: {video_file_path}...")
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
    
    # 2. Upload Phase (Aap yahan apni generated ya test video file ka path denge)
    # video_path = "output.mp4"
    # if os.path.exists(video_path):
    #     upload_to_youtube(video_path, title, description)
    # else:
    #     print(f"Warning: Video file '{video_path}' not found. Skipping upload step for now.")
