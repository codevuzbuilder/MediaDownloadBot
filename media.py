import glob
import os
import subprocess

import yt_dlp

EFFECTS = {
    "slowed": ("🐢 Slowed", "atempo=0.85,aecho=0.6:0.5:400:0.25"),
    "remix": ("🚀 Remix", "atempo=1.08,bass=g=8,treble=g=2"),
    "hall": ("🏟 Concert hall", "aecho=0.8:0.88:60|120|1000:0.4|0.3|0.2"),
    "bass": ("🔊 Bass", "bass=g=12"),
    "nightcore": ("⚡ Nightcore", "asetrate=44100*1.25,aresample=44100"),
}


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True, timeout=900)


def _largest(d, exts):
    files = [p for p in glob.glob(os.path.join(d, "*")) if p.lower().endswith(exts)]
    return max(files, key=os.path.getsize) if files else None


def _ydl(opts, url):
    base = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30}
    base.update(opts)
    with yt_dlp.YoutubeDL(base) as y:
        return y.extract_info(url, download=True)


def download_video(url, d):
    info = _ydl({
        "outtmpl": os.path.join(d, "v.%(ext)s"),
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "merge_output_format": "mp4",
    }, url)
    return _largest(d, (".mp4", ".mkv", ".webm", ".mov")), info.get("title", "video")


def download_audio(query, d):
    info = _ydl({
        "outtmpl": os.path.join(d, "a.%(ext)s"),
        "format": "bestaudio/best",
        "default_search": "ytsearch1",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                            "preferredquality": "192"}],
    }, query)
    if "entries" in info:
        info = next((e for e in info["entries"] if e), {})
    return _largest(d, (".mp3",)), info.get("title", "audio")


def audio_effect(src, key, d):
    out = os.path.join(d, f"{key}.mp3")
    _ff("-i", src, "-vn", "-af", EFFECTS[key][1], "-b:a", "192k", out)
    return out


def extract_audio(src, d):
    out = os.path.join(d, "song.mp3")
    _ff("-i", src, "-vn", "-b:a", "192k", out)
    return out


def circle(src, d):
    """Kvadratga kesadi (Telegram uni doira qilib ko'rsatadi), 60 soniyagacha."""
    out = os.path.join(d, "circle.mp4")
    _ff("-t", "60", "-i", src,
        "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=384:384,setsar=1",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", out)
    return out