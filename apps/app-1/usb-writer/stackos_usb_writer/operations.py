"""Non-destructive helpers shared by the GUI and privileged worker."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable


CHUNK_SIZE = 4 * 1024 * 1024


def sha256_file(
    path: str,
    progress: Callable[[int, int], None] | None = None,
) -> str:
    source = Path(path)
    total = source.stat().st_size
    processed = 0
    digest = hashlib.sha256()
    with source.open("rb", buffering=0) as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
            processed += len(chunk)
            if progress:
                progress(processed, total)
    return digest.hexdigest()


def validate_image(path: str) -> Path:
    image = Path(path).resolve(strict=True)
    if not image.is_file():
        raise ValueError("A imagem selecionada não é um arquivo.")
    if image.suffix.lower() not in {".iso", ".img"}:
        raise ValueError("Selecione um arquivo ISO ou IMG.")
    if image.stat().st_size <= 0:
        raise ValueError("A imagem está vazia.")
    return image


def compare_stream_prefix(
    image_path: str,
    device_path: str,
    progress: Callable[[int, int], None] | None = None,
) -> bool:
    image = validate_image(image_path)
    total = image.stat().st_size
    processed = 0
    with image.open("rb", buffering=0) as source, open(
        device_path, "rb", buffering=0
    ) as target:
        while source_chunk := source.read(CHUNK_SIZE):
            target_chunk = target.read(len(source_chunk))
            if source_chunk != target_chunk:
                return False
            processed += len(source_chunk)
            if progress:
                progress(processed, total)
    return True
