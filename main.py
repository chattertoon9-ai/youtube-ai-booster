import os
import time
import random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from google import genai
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from gtts import gTTS

# MoviePy modern imports
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.audio.AudioClip import CompositeAudioClip
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
    
    # Prompt updated to strictly avoid duplication and ensure unique real-world facts
    prompt = (
        "Create an extremely engaging, high-retention 30-second YouTube Short script about a completely unique, mind-blowing real-world fact, "
        "hidden historical truth, unsolved mystery, or terrifying psychological fact. Do NOT repeat previous topics. "
        "Start with a strong psychological hook or mind-bending question in the first 3 seconds.\n\n"
        "Format your output strictly as follows:\n"
        "TITLE: [Catchy viral title with emojis #shorts]\n"
        "DESCRIPTION: [Engaging description optimized for viral reach, loaded with #shorts #facts #mystery #history #viral]\n"
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
                description = "#shorts #mystery #facts #viral"
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
    """Returns a random unique script from a diverse pool to prevent duplication."""
    fallback_topics = [
        (
            "The Country With No Official Language 🇺🇸🤫 #shorts",
            "Did you know the United States has no official national language? #shorts #facts #history #viral",
            "Did you know that the United States does not actually have an official language at the federal level? "
            "Despite English being widely spoken and used in government, the US Constitution and federal laws "
            "have never declared any official national language. Individual states can choose their own, "
            "but the entire country has no official tongue. "
            "Subscribe for more mind-blowing historical secrets."
        ),
        (
            "The Terrifying Glitch in Human Memory 🧠⚠️ #shorts",
            "Have you ever experienced the Mandela effect? Here is the truth about your brain. #shorts #mystery #facts #viral",
            "Did you know your brain is actively rewriting your memories every single day? "
            "Scientists discovered that every time you recall a memory, you aren't remembering the original event—you are remembering the last time you thought about it. "
            "This means a huge portion of what you believe happened in your past never actually occurred the way you remember it. "
            "Subscribe for more dark psychological facts."
        ),
        (
            "The Secret Deep Sea Anomaly Nobody Talks About 🌊⚓ #shorts",
            "What is hiding at the bottom of the ocean? #shorts #mystery #ocean #viral",
            "Did you know we know less about the deep ocean floor than we do about the surface of Mars? "
            "More than eighty percent of our oceans remain completely unmapped and unexplored. "
            "Deep beneath the crushing pressure, scientists frequently pick up unexplained acoustic anomalies and mysterious sounds "
            "that modern science still cannot identify. What secrets are lurking in the dark abyss? "
            "Subscribe for more unsolved mysteries."
        )
    ]
    return random.choice(fallback_topics)

def download_pixabay_image(query_keyword="mystery history dark cinematic", output_filename="bg_reference.jpg"):
    """Fetches high-vibrant professional photo background from Pixabay API with enhanced clarity and brightness."""
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "58493789-48e94ff1d6193dbd5fce48fc5").strip()
    
    search_queries = [
        "vibrant cinematic mystery 4k", 
        "dramatic historical architecture 4k", 
        "epic dark fantasy background", 
        "stunning cinematic vintage secret"
    ]
    selected_query = random.choice(search_queries)
    
    api_url = f"https://pixabay.com/api/?key={pixabay_key}&q={requests.utils.quote(selected_query)}&image_type=photo&orientation=vertical&safesearch=true&per_page=15"
    
    try:
        print(f"Searching Pixabay for vibrant image: '{selected_query}'...")
        res = requests.get(api_url, timeout=15)
        if res.status_code == 200:
            data = res.json()
            hits = data.get("hits", [])
            if hits:
                img_item = random.choice(hits)
                img_url = img_item.get("largeImageURL") or img_item.get("webformatURL")
                if img_url:
                    img_res = requests.get(img_url, timeout=15)
                    if img_res.status_code == 200:
                        with open(output_filename, "wb") as f:
                            f.write(img_res.content)
                        
                        # Process image: Enhance contrast and use a lighter overlay so images are bright & sharp
                        img = Image.open(output_filename).convert("RGBA")
                        img = img.resize((1080, 1920), Image.Resampling.LANCZOS)
                        
                        enhancer = ImageEnhance.Contrast(img)
                        img = enhancer.enhance(1.25) # Boost contrast for vibrant look
                        
                        # Light overlay so background remains clear and colorful
                        overlay = Image.new("RGBA", img.size, (10, 10, 20, 80))
                        img = Image.alpha_composite(img, overlay)
                        img.convert("RGB").save(output_filename)
                        print("Vibrant Pixabay background image downloaded and enhanced!")
                        return output_filename
    except Exception as e:
        print(f"Pixabay API notice: {str(e)}")
        
    return None

def download_background_music(output_filename="bg_music.mp3"):
    """Downloads a royalty-free suspenseful background music track."""
    music_urls = [
        "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf756.mp3?filename=cinematic-time-suspense-115990.mp3",
        "https://cdn.pixabay.com/download/audio/2022/03/15/audio_c8c365825d.mp3?filename=mystery-brand-110846.mp3"
    ]
    selected_url = random.choice(music_urls)
    try:
        print("Downloading background suspense music...")
        res = requests.get(selected_url, timeout=15)
        if res.status_code == 200:
            with open(output_filename, "wb") as f:
                f.write(res.content)
            print("Background music downloaded successfully!")
            return output_filename
    except Exception as e:
        print(f"Background music download notice: {str(e)}")
