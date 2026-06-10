from mutagen import File
from pathlib import Path


def extract_audio_metadata(file_path):
    audio = File(file_path)

    if audio is None:
        return None

    metadata = {
        "duration_ms": int(audio.info.length * 1000) if audio.info else None,
        "title": None,
        "track_number": None,
        "disc_number": None,
    }

    if audio.tags:
        metadata["title"] = audio.tags.get("TIT2", [None])[0]
        metadata["track_number"] = _safe_int(audio.tags.get("TRCK"))
        metadata["disc_number"] = _safe_int(audio.tags.get("TPOS"))

    return metadata


def _safe_int(tag):
    if not tag:
        return None
    try:
        value = str(tag[0]).split("/")[0]
        return int(value)
    except Exception:
        return None
