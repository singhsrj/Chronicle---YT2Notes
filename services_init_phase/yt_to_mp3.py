import yt_dlp
import os
import sys


def download_yt_as_mp3(url: str, output_folder: str = "downloads"):
    """
    Downloads a YouTube video and converts it to MP3 format.
    """

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("\nDownload and conversion completed successfully.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python yt_to_mp3.py <YouTube_URL>")
        sys.exit(1)

    video_url = sys.argv[1]
    download_yt_as_mp3(video_url)