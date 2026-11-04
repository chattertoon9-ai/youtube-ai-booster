import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

def upload_to_youtube(video_path, title, description="Automated upload via Python script"):
    print("Uploading video to YouTube...")
    
    # Credentials GitHub Secrets ya environment variables se liye jayenge
    # (Local testing ke liye OAuth token file ya Service Account use hota hai)
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
            'tags': ['automation', 'shorts', 'ai'],
            'categoryId': '22'  # 22 category code People & Blogs ke liye hai
        },
        'status': {
            'privacyStatus': 'public', # 'private', 'unlisted', ya 'public'
            'selfDeclaredMadeForKids': False
        }
    }

    # Media file upload setup (Resumable upload for large files)
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')

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

    print(f"Video uploaded successfully! Video ID: {response.get('id')}")

# Main execution ke aakhir mein ise call karein:
if __name__ == "__main__":
    topic = "3 Unknown Secrets About AI"
    bg_image = "background.jpg"
    
    # 1. Script generate karein
    script = generate_script(topic)
    
    # 2. Voiceover banayein
    audio_file = create_voiceover(script)
    
    # 3. Video render karein
    output_video = "final_video.mp4"
    create_video(audio_file, bg_image, output_video)
    
    # 4. YouTube par upload karein
    # upload_to_youtube(output_video, title=topic)
