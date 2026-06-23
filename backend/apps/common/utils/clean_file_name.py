import re
from urllib.parse import quote
from django.http import HttpResponse, Http404
import mimetypes


def get_clean_download_filename(track):
    ext = track.audio_file.name.split('.')[-1].lower() if track.audio_file else "mp3"
    artist_name = "Unknown Artist"
    if track.singer:
        artist_name = track.singer.name
    elif track.composer:
        artist_name = track.composer.name
    elif track.album and track.album.artist:
        artist_name = track.album.artist.name

    title = track.title if track.title else "Untitled"

    raw_name = f"{artist_name} - {title}"

    safe_name = re.sub(r'[\\/*?:"<>|]', "", raw_name)

    return f"{safe_name}.{ext}"