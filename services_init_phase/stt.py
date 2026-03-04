#this script ingests audio files and transcribes them using the OpenAI Whisper API

import whisper
'''
ffmpeg version 7.1-essentials_build-www.gyan.dev Copyright (c) 2000-2024 the FFmpeg developers
built with gcc 14.2.0 (Rev1, Built by MSYS2 project)
'''

model = whisper.load_model("base")
result = model.transcribe("audio.mp3")
print(result["text"])

