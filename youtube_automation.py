import os
import time
from google import genai

def generate_viral_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY environment variable is missing.")
    
    # New official google-genai client initialization
    client = genai.Client(api_key=api_key)
    
    # Priority list including 3.8 and all fallback models
    models_to_try = [
        'gemini-3.8-flash',
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
        'gemini-1.5-pro'
    ]
    
    prompt = (
        "Generate a short, viral YouTube Shorts script with an engaging title. "
        "Format the output strictly as:\nTitle: [Your Title Here]\n\n[Your Script Here]"
    )
    
    for model_name in models_to_try:
        attempts = 2
        for attempt in range(attempts):
            try:
                print(f"Trying model: {model_name} (Attempt {attempt+1}/{attempts})...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                
                if response and response.text:
                    print(f"Successfully generated content using {model_name}")
                    text = response.text.strip()
                    
                    if "Title:" in text:
                        parts = text.split("\n\n", 1)
                        title = parts[0].replace("Title:", "").strip()
                        script = parts[1].strip() if len(parts) > 1 else "Keep pushing forward!"
                    else:
                        title = "Viral Short #shorts"
                        script = text
                        
                    return title, script
                    
            except Exception as e:
                print(f"Model {model_name} failed with error: {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    wait_time = 20 * (attempt + 1)
                    print(f"Rate limit hit. Waiting for {wait_time} seconds before trying next...")
                    time.sleep(wait_time)
                else:
                    time.sleep(2)
                    
    raise Exception("All Gemini models failed due to rate limits or availability. Please try again later.")

if __name__ == "__main__":
    print("AI is generating a viral script...")
    title, script = generate_viral_content()
    print(f"Generated Title: {title}")
    print(f"Generated Script Length: {len(script)} characters")
