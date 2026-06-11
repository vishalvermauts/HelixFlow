import sys
import httpx
import time

# Default target: local or remote
DEFAULT_URL = "http://localhost:8000"
TOKEN = "YOUR_API_KEY_HERE"

def send_request(base_url, model, prompt, project="default", tags="env:production"):
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "X-Project": project,
        "X-Tags": tags
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    
    print(f"Sending request to model '{model}' for project '{project}'... (Prompt len: {len(prompt)} characters)")
    start = time.time()
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=20.0)
        dur = int((time.time() - start) * 1000)
        print(f"Response Status: {r.status_code} | Latency: {dur}ms")
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            print(f"Reply snippet: {content[:80]}...\n")
        else:
            print(f"Error Response: {r.text}\n")
    except Exception as e:
        print(f"Request failed: {e}\n")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print(f"==========================================================")
    print(f"🧬 HELIXFLOW TRAFFIC GENERATOR")
    print(f"Target Gateway: {target}")
    print(f"==========================================================\n")
    
    # 1. Short prompt -> DeepSeek (fabric-speed-edge)
    send_request(target, "deepseek-chat", "What is the capital of Australia?", "customer-portal", "env:production,tier:premium")
    
    # 2. Short prompt -> DeepSeek
    send_request(target, "auto", "Give me a one-sentence programming quote.", "website-analytics", "env:staging,tier:free")
    
    # 3. Long prompt -> Gemini (fabric-dense-reasoning)
    long_prompt = "Explain in extreme detail how the TCP/IP three-way handshake works. " * 8
    send_request(target, "deepseek-chat", long_prompt, "api-platform", "env:production,tier:enterprise")

    # 4. Long prompt -> Gemini
    long_prompt_2 = "Write a comprehensive essay describing the historical evolution of artificial intelligence from the Turing Test to modern Large Language Models, detailing the shifts in architectures and neural network concepts. " * 4
    send_request(target, "auto", long_prompt_2, "customer-portal", "env:production,tier:premium")
    
    print("==========================================================")
    print("🎉 Done! Check your HelixFlow Web UI to see the live metrics.")
    print("==========================================================")
