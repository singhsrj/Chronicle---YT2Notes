import os
import json
import subprocess
from faster_whisper import WhisperModel

# ---------------- CONFIG ---------------- #
VIDEO_URL = input("Enter YouTube URL: ")
CHUNK_SECONDS = 300  # 5 minutes
MODEL_NAME = "base"  # Options: tiny, base, small, medium, large-v2, large-v3
CHECKPOINT_FILE = "checkpoint.json"
OUTPUT_FILE = "final_transcript.txt"
OUTPUT_JSON = "final_transcript.json"  # Structured output with timestamps
CHUNK_DIR = "chunks"
# ---------------------------------------- #

os.makedirs(CHUNK_DIR, exist_ok=True)

# ---------------- STEP 1: DOWNLOAD AUDIO ---------------- #
print("Downloading audio...")

download_cmd = [
    "yt-dlp",
    "-f", "bestaudio",
    "--extract-audio",
    "--audio-format", "wav",
    "--audio-quality", "0",
    "-o", "full_audio.%(ext)s",
    VIDEO_URL
]

subprocess.run(download_cmd)

print("Audio downloaded.")

# ---------------- STEP 2: CONVERT TO 16kHz MONO ---------------- #
print("Converting to 16kHz mono WAV...")

subprocess.run([
    "ffmpeg",
    "-y",
    "-i", "full_audio.wav",
    "-ar", "16000",
    "-ac", "1",
    "processed.wav"
])

# ---------------- STEP 3: SPLIT INTO CHUNKS ---------------- #
print("Splitting into chunks...")

subprocess.run([
    "ffmpeg",
    "-i", "processed.wav",
    "-f", "segment",
    "-segment_time", str(CHUNK_SECONDS),
    "-c", "copy",
    f"{CHUNK_DIR}/chunk_%03d.wav"
])

# Remove large files immediately
os.remove("full_audio.wav")
os.remove("processed.wav")

print("Chunking completed.")

# ---------------- STEP 4: LOAD FASTER-WHISPER MODEL ---------------- #
print(f"Loading Faster-Whisper model ({MODEL_NAME})...")
model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
print("Model loaded successfully.")

# ---------------- STEP 5: CHECKPOINT LOAD ---------------- #
start_index = 0
all_segments = []

if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        checkpoint = json.load(f)
        start_index = checkpoint["last_completed_chunk"] + 1
        all_segments = checkpoint.get("segments", [])
        print(f"Resuming from chunk {start_index}")

# ---------------- STEP 6: STREAM TRANSCRIPTION ---------------- #
chunks = sorted(os.listdir(CHUNK_DIR))
total_chunks = len(chunks)

print(f"\n{'='*60}")
print(f"Starting transcription pipeline: {total_chunks} chunks")
print(f"{'='*60}\n")

for i, chunk_file in enumerate(chunks):
    if i < start_index:
        continue

    chunk_path = os.path.join(CHUNK_DIR, chunk_file)
    chunk_offset = i * CHUNK_SECONDS  # Time offset for this chunk

    print(f"[{i+1}/{total_chunks}] Processing {chunk_file}...")

    # Transcribe chunk with faster-whisper (returns generator of segments)
    segments, info = model.transcribe(
        chunk_path,
        beam_size=5,
        language="en",  # Auto-detect if None
        condition_on_previous_text=True
    )

    # Stream segments as they come
    chunk_text = []
    chunk_segments = []

    for segment in segments:
        # Adjust timestamps to global timeline
        global_start = chunk_offset + segment.start
        global_end = chunk_offset + segment.end
        
        segment_data = {
            "start": global_start,
            "end": global_end,
            "text": segment.text.strip()
        }
        
        chunk_segments.append(segment_data)
        chunk_text.append(segment.text.strip())
        
        # Print progress in real-time
        print(f"  [{global_start:.2f}s -> {global_end:.2f}s] {segment.text.strip()}")

    # Append to transcript file progressively
    full_chunk_text = " ".join(chunk_text)
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(full_chunk_text + "\n\n")

    # Accumulate all segments
    all_segments.extend(chunk_segments)

    # Save checkpoint (with segments for resume capability)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({
            "last_completed_chunk": i,
            "total_chunks": total_chunks,
            "segments": all_segments,
            "video_url": VIDEO_URL
        }, f, indent=2)

    # Delete chunk immediately to save space
    os.remove(chunk_path)
    print(f"  ✓ Chunk {i+1} completed and removed.\n")

# ---------------- STEP 7: FINALIZE ---------------- #
print(f"{'='*60}")
print("✓ Transcription pipeline complete!")
print(f"{'='*60}\n")

# Save structured JSON output with all segments
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump({
        "video_url": VIDEO_URL,
        "total_segments": len(all_segments),
        "total_duration": all_segments[-1]["end"] if all_segments else 0,
        "segments": all_segments
    }, f, indent=2, ensure_ascii=False)

print(f"📄 Text transcript saved to: {OUTPUT_FILE}")
print(f"📊 Structured JSON saved to: {OUTPUT_JSON}")
print(f"📝 Total segments: {len(all_segments)}")

# Clean up checkpoint file
if os.path.exists(CHECKPOINT_FILE):
    os.remove(CHECKPOINT_FILE)
    print(f"🗑️  Checkpoint file removed.")

# Clean up chunk directory
if os.path.exists(CHUNK_DIR):
    os.rmdir(CHUNK_DIR)
    print(f"🗑️  Chunk directory removed.")

print("\n✅ Pipeline completed successfully!")