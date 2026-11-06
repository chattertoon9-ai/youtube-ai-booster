import os
import time
import google.generativeai as genai

def generate_viral_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY environment variable is missing.")
    
    genai.configure(api_key=api_key)
    
    # Active model for free tier
    models_to_try = [
        'gemini-3.8-flash'
    ]
    
    prompt = (
        "Generate a short, viral YouTube Shorts script with an engaging title. "
        "Format the output strictly as:\nTitle: [Your Title Here]\n\n[Your Script Here]"
    )
    
    for model_name in models_to_try:
        attempts = 3
        for attempt in range(attempts):
            try:
                print(f"Trying model: {model_name} (Attempt {attempt+1}/{attempts})...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                
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
                print(f"Attempt {attempt+1} failed with error: {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    wait_time = 45 * (attempt + 1)
                    print(f"Rate limit hit. Waiting for {wait_time} seconds before retrying...")
                    time.sleep(wait_time)
                else:
                    time.sleep(5)
                
    raise Exception("Gemini API rate limit exceeded. Please wait a minute and re-run the workflow.")

if __name__ == "__main__":
    print("AI is generating a viral script...")
    title, script = generate_viral_content()
    print(f"Generated Title: {title}")
    print(f"Generated Script Length: {len(script)} characters")
