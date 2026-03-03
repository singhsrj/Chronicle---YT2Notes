"""
Test client for Long Video Transcription API
"""
import requests
import time
import sys

API_BASE = "http://localhost:8000/api/long-video"


def test_transcription(video_url: str, model: str = "base"):
    """Test the complete transcription flow."""
    
    print("=" * 60)
    print("YT Video Transcription Test")
    print("=" * 60)
    print(f"Video URL: {video_url}")
    print(f"Model: {model}")
    print()
    
    # 1. Start transcription
    print("📤 Starting transcription...")
    try:
        response = requests.post(
            f"{API_BASE}/transcribe",
            json={
                "url": video_url,
                "model_name": model,
                "chunk_seconds": 300,
                "language": "en"
            }
        )
        response.raise_for_status()
        data = response.json()
        session_id = data["session_id"]
        print(f"✅ Session created: {session_id}")
        print()
    except Exception as e:
        print(f"❌ Failed to start transcription: {e}")
        return
    
    # 2. Poll status
    print("⏳ Monitoring progress...")
    print("-" * 60)
    
    last_status = None
    while True:
        try:
            response = requests.get(f"{API_BASE}/status/{session_id}")
            response.raise_for_status()
            status = response.json()
            
            current_status = status["status"]
            
            # Print status updates
            if current_status != last_status:
                print(f"\n📊 Status: {current_status.upper()}")
                last_status = current_status
            
            # Print progress if available
            if status.get("progress"):
                prog = status["progress"]
                percentage = prog["progress_percentage"]
                current = prog["completed_chunks"]
                total = prog["total_chunks"]
                
                bar_length = 40
                filled = int(bar_length * percentage / 100)
                bar = "█" * filled + "░" * (bar_length - filled)
                
                print(f"\r   [{bar}] {percentage:.1f}% ({current}/{total} chunks)", end="", flush=True)
            
            # Check completion
            if current_status == "completed":
                print("\n\n✅ Transcription completed!")
                break
            elif current_status == "error":
                print(f"\n\n❌ Error: {status.get('error', 'Unknown error')}")
                return
            
            time.sleep(3)
            
        except Exception as e:
            print(f"\n❌ Error checking status: {e}")
            return
    
    print("-" * 60)
    print()
    
    # 3. Get result
    print("📥 Fetching results...")
    try:
        response = requests.get(f"{API_BASE}/result/{session_id}")
        response.raise_for_status()
        result = response.json()
        
        print(f"✅ Transcription complete!")
        print()
        print(f"📊 Statistics:")
        print(f"   • Total segments: {result['total_segments']}")
        print(f"   • Total duration: {result['total_duration']:.1f} seconds ({result['total_duration']/60:.1f} minutes)")
        print(f"   • Text length: {len(result['full_text'])} characters")
        print()
        
        # Show first few segments
        print("📝 First 3 segments:")
        for i, segment in enumerate(result["segments"][:3], 1):
            print(f"   {i}. [{segment['start']:.1f}s - {segment['end']:.1f}s]")
            print(f"      {segment['text']}")
        print()
        
    except Exception as e:
        print(f"❌ Error fetching result: {e}")
        return
    
    # 4. Download files
    print("💾 Downloading files...")
    try:
        # Download text
        response = requests.get(f"{API_BASE}/download/text/{session_id}")
        response.raise_for_status()
        with open(f"{session_id}_transcript.txt", "wb") as f:
            f.write(response.content)
        print(f"   ✅ Text saved: {session_id}_transcript.txt")
        
        # Download JSON
        response = requests.get(f"{API_BASE}/download/json/{session_id}")
        response.raise_for_status()
        with open(f"{session_id}_transcript.json", "wb") as f:
            f.write(response.content)
        print(f"   ✅ JSON saved: {session_id}_transcript.json")
        print()
        
    except Exception as e:
        print(f"❌ Error downloading files: {e}")
        return
    
    print("=" * 60)
    print("🎉 Test completed successfully!")
    print("=" * 60)
    print()
    print(f"Session ID: {session_id}")
    print(f"Files saved in current directory")
    print()


def list_sessions():
    """List all active sessions."""
    print("📋 Active Sessions:")
    print("-" * 60)
    
    try:
        response = requests.get(f"{API_BASE}/sessions")
        response.raise_for_status()
        data = response.json()
        
        if not data["sessions"]:
            print("No active sessions")
            return
        
        for session in data["sessions"]:
            print(f"\n🔹 {session['session_id']}")
            print(f"   Status: {session['status']}")
            print(f"   Progress: {session['progress_percentage']:.1f}%")
            print(f"   URL: {session['video_url']}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error listing sessions: {e}")


def check_health():
    """Check if API is running."""
    print("🏥 Checking API health...")
    try:
        response = requests.get("http://localhost:8000/health")
        response.raise_for_status()
        print("✅ API is running!")
        print(response.json())
        return True
    except Exception as e:
        print(f"❌ API is not accessible: {e}")
        print("\nMake sure to start the server:")
        print("  cd backend")
        print("  python main.py")
        return False


if __name__ == "__main__":
    # Check API health first
    if not check_health():
        sys.exit(1)
    
    print("\n")
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            list_sessions()
        
        elif command == "test" and len(sys.argv) > 2:
            video_url = sys.argv[2]
            model = sys.argv[3] if len(sys.argv) > 3 else "base"
            test_transcription(video_url, model)
        
        else:
            print("Usage:")
            print("  python test_client.py test <youtube_url> [model_name]")
            print("  python test_client.py list")
            print()
            print("Examples:")
            print("  python test_client.py test https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            print("  python test_client.py test https://www.youtube.com/watch?v=dQw4w9WgXcQ small")
            print("  python test_client.py list")
    
    else:
        print("Usage:")
        print("  python test_client.py test <youtube_url> [model_name]")
        print("  python test_client.py list")
        print()
        print("Examples:")
        print("  python test_client.py test https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        print("  python test_client.py test https://www.youtube.com/watch?v=dQw4w9WgXcQ small")
        print("  python test_client.py list")
