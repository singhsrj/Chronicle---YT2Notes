from faster_whisper import WhisperModel

model = WhisperModel("small")

segments, info = model.transcribe("E:/YT VIDEOS TO NOTES APP/services/audio.mp3")
for segment in segments:
    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
