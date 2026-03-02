import os
from google import genai
from dotenv import load_dotenv

def test_key(key, label):
    print(f"--- Testing {label}: {key[:10]}... ---")
    client = genai.Client(api_key=key)
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents="Hi")
        print(f"✅ {label} is WORKING!")
        print(f"Response: {response.text[:50]}...")
        return True
    except Exception as e:
        print(f"❌ {label} FAILED: {str(e)[:200]}")
        return False

if __name__ == "__main__":
    # Key in line 14
    key1 = "AIzaSyAaszPFW0U9EyPfmUQuakSxcWuodUXB6WI"
    # Key in line 15
    key2 = "AIzaSyAuNTqRdpjNGBQoQ6D-7eDvWBbb1aycOk4"

    
    test_key(key1, "Key 1 (Line 14)")
    test_key(key2, "Key 2 (Line 15)")
