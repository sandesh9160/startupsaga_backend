# 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
import requests

API_KEY = "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"  # or use os.getenv()

url = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": "z-ai/glm-4.5-air:free",
    "messages": [
        {"role": "user", "content": "Test connection"}
    ]
}

response = requests.post(url, headers=headers, json=payload)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())