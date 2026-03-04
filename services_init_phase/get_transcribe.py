from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse, parse_qs

def extract_video_id(url_or_id: str) -> str:
    """
    Parse a YouTube video ID from a URL or return the ID directly.
    
    Supports formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    - Raw video ID (e.g. -jCQerxzF48)
    """
    # If it looks like a plain video ID already (11 chars, alphanumeric + - _)
    if re.match(r'^[A-Za-z0-9_-]{11}$', url_or_id):
        return url_or_id
    parsed = urlparse(url_or_id)
    if parsed.netloc in ('youtu.be', 'www.youtu.be'):
        return parsed.path.lstrip('/')
    if 'youtube.com' in parsed.netloc:
        qs = parse_qs(parsed.query)
        if 'v' in qs:
            return qs['v'][0]
        path_parts = parsed.path.strip('/').split('/')
        if path_parts[0] in ('embed', 'shorts', 'v') and len(path_parts) > 1:
            return path_parts[1]
    raise ValueError(f"Could not extract video ID from: {url_or_id}")


def ingest_transcript(url_or_id: str) -> str:
    video_id = extract_video_id(url_or_id)
    print(f"Fetching transcript for video ID: {video_id}")

    api = YouTubeTranscriptApi()
    transcript_list = api.list(video_id)

    # Try en variants first, then fall back to any available language
    try:
        transcript = transcript_list.find_transcript(["en", "en-US", "en-GB"])
    except Exception:
        # Grab the first available transcript (any language)
        transcript = next(iter(transcript_list))
        print(f"Falling back to language: {transcript.language} ({transcript.language_code})")

    fetched = transcript.fetch()
    full_text = " ".join([t.text for t in fetched])
    return full_text


# --- Main script ---
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Use command-line argument
        url_or_id = sys.argv[1]
    else:
        # Prompt for input
        url_or_id = input("Enter YouTube URL or video ID: ").strip()
    
    if not url_or_id:
        print("Error: No URL or video ID provided.")
        sys.exit(1)
    
    try:
        print(f"\nFetching transcript for: {url_or_id}")
        print("-" * 60)
        
        video_id = extract_video_id(url_or_id)
        print(f"Video ID: {video_id}")
        
        text = ingest_transcript(url_or_id)
        
        print(f"\n{'='*60}")
        print(f"TRANSCRIPT ({len(text)} characters)")
        print(f"{'='*60}\n")
        print(text)
        
        # Optionally save to file
        save = input("\n\nSave to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = f"{video_id}_transcript.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"✅ Saved to: {filename}")
    
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to fetch transcript: {e}")
        sys.exit(1)