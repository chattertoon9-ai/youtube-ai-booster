import os
from google import genai

# Aapki maujooda 6 keys ko environment variables se fetch karna
api_keys = [
    os.getenv("GEMINI_API_KEY"),
    os.getenv("GEMINI_API_KEY_2"),
    os.getenv("GEMINI_API_KEY_3"),
    os.getenv("GEMINI_API_KEY_4"),
    os.getenv("GEMINI_API_KEY_5"),
    os.getenv("GEMINI_API_KEY_6"),
]

# Agar koi secret khali/missing ho toh usey list se nikal dena
api_keys = [key for key in api_keys if key]

if not api_keys:
    raise ValueError("Critical Error: Koi bhi Gemini API key configure nahi ki gayi hai!")

def generate_with_rotation(prompt_text):
    """
    Ek ek karke sabhi keys ko try karega. Agar kisi ek key par 
    error aaye toh script rukne ke bajaye agli key par chali jayegi.
    """
    for index, key in enumerate(api_keys):
        try:
            print(f"Active Key # {index + 1} ka istemal kiya ja raha hai...")
            
            # Naya aur official `google-genai` client initialization
            client = genai.Client(api_key=key)
            
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt_text,
            )
            
            print("Successfully content generate ho gaya!")
            return response.text
            
        except Exception as e:
            print(f"Warning: Key # {index + 1} fail ho gayi. Error: {e}")
            continue # Foran agli key par switch ho jao
            
    raise Exception("Critical Error: Tamam active API keys par request fail ho chuki hain!")

# Yahan se aapka main execution shuru hota hai
if __name__ == "__main__":
    # Apne script generate karne ka function yahan call karein
    prompt = "Generate a viral script for YouTube."
    
    try:
        script_output = generate_with_rotation(prompt)
        print("\n--- Generated Script Output ---")
        print(script_output)
        
        # Agar aapko is output ko kisi file me save karna ho ya aage process karna ho:
        # with open("generated_script.txt", "w", encoding="utf-8") as f:
        #     f.write(script_output)
            
    except Exception as err:
        print(f"Process Failed: {err}")
        exit(1)
