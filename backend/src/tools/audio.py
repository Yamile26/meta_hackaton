"""Validación de audio subido y conversión a WAV mono 24 kHz con ffmpeg."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

ALLOWED_FORMATS = ("webm", "m4a", "mp3", "wav")
FFMPEG_TIMEOUT_S = 60


class AudioError(ValueError):
    """Audio inválido o conversión fallida. El mensaje es apto para el usuario."""


def sniff_format(head: bytes) -> Optional[str]:
    """Detecta el formato por los bytes iniciales (no se confía en extensión ni content-type)."""
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "m4a"
    if head[:3] == b"ID3" or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    return None


def ffmpeg_command(ffmpeg: str, src: Path, dst: Path) -> list[str]:
    return [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(src),
        "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", "-map_metadata", "-1",
        str(dst),
    ]


def convert_to_wav(src: Path, dst: Path, ffmpeg: Optional[str] = None) -> Path:
    """Convierte `src` a WAV mono PCM 16 bits 24 kHz. Sin shell; argumentos en lista."""
    exe = ffmpeg or shutil.which("ffmpeg")
    if not exe:
        raise AudioError("ffmpeg no está instalado en el servidor")
    try:
        proc = subprocess.run(
            ffmpeg_command(exe, src, dst), capture_output=True, timeout=FFMPEG_TIMEOUT_S, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AudioError("La conversión de audio tardó demasiado") from exc
    except OSError as exc:
        raise AudioError("ffmpeg no está disponible en el servidor") from exc
    if proc.returncode != 0 or not dst.is_file():
        raise AudioError("No se pudo convertir el audio")
    return dst
