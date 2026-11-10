"""Private storage and audio sniffing for voice notes."""

import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage

# extension -> served content type
AUDIO_TYPES = {
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "aac": "audio/aac",
}


class PrivateMediaStorage(FileSystemStorage):
    """Files under PRIVATE_MEDIA_ROOT (read live, so tests can redirect it).

    There is deliberately no public URL: files leave only via authorized views.
    """

    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private files have no public URL.")


def private_storage():
    return PrivateMediaStorage()


def voice_note_path(instance, filename):
    # Generated name; the client's file name is never used on disk.
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    return f"voice-notes/{uuid.uuid4().hex}.{ext}"


def detect_audio_type(head: bytes) -> str | None:
    """Identify the container from magic bytes (client Content-Type is not trusted)."""
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"  # Matroska/WebM (Chrome, Firefox MediaRecorder)
    if head.startswith(b"OggS"):
        return "ogg"
    if head[4:8] == b"ftyp":
        return "m4a"  # MP4 audio (Safari MediaRecorder)
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"ID3"):
        return "mp3"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0:
        return "aac"  # ADTS frame (layer bits 00)
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "mp3"  # MPEG audio frame sync
    return None
