import os
from google import genai
from gtts import gTTS
from moviepy.editor import AudioFileClip, ImageClip, CompositeVideoClip, TextClip

# 1. Gemini Client Initialize
client = genai.Client()

def generate_script(topic):
    prompt = f"""
    Write a short, engaging YouTube Shorts/Video script about: "{topic}".
    Write ONLY narration text for voiceover. No visual cues, no brackets, no labels.
    Keep it within 100 words.
    """
    print("Generating script with Gemini...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()

def create_voiceover(text, audio_path="voiceover.mp3"):
    print("Generating voiceover...")
    clean_text = text.replace("*", "").replace("#", "")
    tts = gTTS(text=clean_text, lang='en', slow=False)
    tts.save(audio_path)
    return audio_path

def create_video(audio_path, image_path, output_path="final_video.mp4"):
    print("Rendering video...")
    # Load audio
    audio_clip = AudioFileClip(audio_path)
    
    # Create image background with duration matching the voiceover
    image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
    
    # Set video audio
    video_clip = image_clip.set_audio(audio_clip)
    
    # Render final MP4 file (FPS 24 standard)
    video_clip.write_videofile(
        output_path, 
        fps=24, 
        codec='libx264', 
        audio_codec='aac'
    )
    
    # Close clips to free RAM
    audio_clip.close()
    video_clip.close()
    print(f"Video rendered successfully: {output_path}")

if __name__ == "__main__":
    topic = "3 Unknown Secrets About AI"
    
    # Path for background image (Aap apne folder mein koi bhi background.jpg rakhein)
    bg_image = "background.jpg" 
    
    if not os.path.exists(bg_image):
        print(f"Warning: Please place a '{bg_image}' file in your project folder!")
    else:
        # 1. Script
        script = generate_script(topic)
        print("\n--- Script ---\n", script, "\n--------------\n")
        
        # 2. Voiceover
        audio_file = create_voiceover(script)
        
        # 3. Video
        create_video(audio_file, bg_image)
