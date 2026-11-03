import os
from google import genai
from gtts import gTTS

# 1. Gemini Client Initialize karein
client = genai.Client()

def generate_youtube_script(topic):
    prompt = f"""
    Write a short, engaging YouTube video script about: "{topic}".
    Format requirements:
    - Include a strong hook in the first 5 seconds.
    - Keep it concise (around 1-2 minutes spoken time).
    - Write ONLY the narration text (do not include visual cues, bracketed text, or speaker labels).
    """
    
    print("Generating script via Gemini API...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text.strip()

def create_voiceover(text, output_filename="voiceover.mp3"):
    print("Generating voiceover audio...")
    # Clean text from any remaining formatting symbols
    clean_text = text.replace("*", "").replace("#", "")
    
    tts = gTTS(text=clean_text, lang='en', slow=False)
    tts.save(output_filename)
    print(f"Voiceover saved as: {output_filename}")

if __name__ == "__main__":
    # Test Topic
    video_topic = "Top 5 Mind-Blowing Facts About Space"
    
    # Run Script Generation
    script_text = generate_youtube_script(video_topic)
    print("\n--- Generated Script ---")
    print(script_text)
    print("------------------------\n")
    
    # Run Voiceover Generation
    create_voiceover(script_text)
