# it ingests txt input and returns the output from ollama which user can interact with via react frontend

import requests

def txt2notes(txt):
    # this function takes txt input and returns the output from ollama with detailed notes
    
    # System prompt for detailed note generation
    system_prompt = """You are an expert note-taker specializing in creating comprehensive, well-structured notes from video transcripts.

Your task is to:
1. Analyze the provided transcript thoroughly
2. Extract all key concepts, ideas, and important information
3. Organize the content into clear, logical sections with headings
4. Include relevant examples, explanations, and context
5. Create detailed bullet points that capture the essence of the content
6. Highlight important terminology and definitions
7. Maintain the flow and structure of the original content
8. Ensure the notes are detailed yet easy to understand

Format the notes with proper markdown formatting including headers, bullet points, and emphasis where appropriate."""
    
    url = "http://localhost:11434/api/generate"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "model": "qwen2.5:7b",  # Change this to your preferred model
        "prompt": txt,
        "system": system_prompt,
        "stream": False
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Request failed with status code {response.status_code}", "details": response.text}

if __name__ == "__main__":
    sample_txt = """In this video, we will explore the fundamentals of machine learning. We will cover the basics of supervised and unsupervised learning, discuss common algorithms such as linear regression and k-means clustering, and provide examples of how these techniques are applied in real-world scenarios. By the end of this video, you will have a solid understanding of the key concepts in machine learning and how to get started with your own projects."""
    result = txt2notes(sample_txt)
    print(result)
