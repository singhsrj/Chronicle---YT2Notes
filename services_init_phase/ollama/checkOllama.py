# this script is used to run ollama in the background and keep it running
# it also provides a function to check if ollama is running and to start it if it's not
import subprocess
import time
import requests

def is_ollama_running():
    """Check if Ollama is running by sending a request to the API."""
    try:
        response = requests.get("http://localhost:11434/v1/models")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    
def start_ollama():
    """Start Ollama in the background."""
    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    if not is_ollama_running():
        print("Ollama is not running. Starting Ollama...")
        start_ollama()
        # Wait for Ollama to start
        time.sleep(5)
        if is_ollama_running():
            print("Ollama started successfully.")
        else:
            print("Failed to start Ollama.")
    else:
        print("Ollama is already running.")