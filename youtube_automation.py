import google.generativeai as genai
import os
import time

def generate_viral_content():
    api_key = os.environ.get("GEMINI_API_KEY")
    genai.configure(api_key=api_key)
    
    # 1.5 se lekar 3.8 tak ke tamam models ki priority list
    models_to_try = [
        'gemini-3.8-flash',
        'gemini-2.5-flash',
        'gemini-2.0-flash-exp',
        'gemini-1.5-flash',
        'gemini-1.5-pro'
    ]
    
    prompt = "Generate a short viral YouTube Shorts script with a title. Return title and script."
    
    for model_name in models_to_try:
        try:
            print(f"Trying model: {model_name}...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                print(f"Successfully generated content using {model_name}")
                content = response.text.split("\n\n")
                title = content[0].replace("Title:", "").strip()
                script = "\n".join(content[1:]).strip()
                return title, script
        except Exception as e:
            print(f"Model {model_name} failed with error: {e}. Trying next model...")
            time.sleep(2)
            
    raise Exception("All Gemini models failed due to high demand or rate limits. Please try again later.")
