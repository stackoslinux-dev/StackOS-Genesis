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


def compare_stream_prefix(
    image_path: str,
    device_path: str,
    progress: Callable[[int, int], None] | None = None,
) -> bool:
    image = validate_image(image_path)
    total = expanded_size(image)
    processed = 0
    with image_stream(image) as source, open(
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

# Imagens brutas e imagens comprimidas de distribuições/arquiteturas diferentes.
import contextlib,gzip,lzma,bz2,zipfile,os

def image_kind(path):
 name=Path(path).name.casefold()
 if name.endswith(('.iso','.img')):return 'raw'
 for extension,kind in [('.gz','gzip'),('.xz','xz'),('.bz2','bzip2')]:
  if name.endswith(('.iso'+extension,'.img'+extension)):return kind
 if name.endswith('.zip'):return 'zip'
 raise ValueError('Use ISO, IMG, ISO/IMG comprimida (GZ/XZ/BZ2) ou ZIP com uma única imagem.')

def validate_image(path):
 image=Path(path).expanduser().resolve(strict=True)
 if not image.is_file() or image.stat().st_size<=0:raise ValueError('A imagem deve ser um arquivo regular não vazio.')
 image_kind(image);return image

def signature(path):
 st=Path(path).stat();return ':'.join(str(v) for v in (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns))

@contextlib.contextmanager
def image_stream(path,fd=None):
 kind=image_kind(path)
 if fd is None:base=open(path,'rb')
 else:os.lseek(fd,0,os.SEEK_SET);base=os.fdopen(os.dup(fd),'rb')
 with base:
  if kind=='raw':yield base
  elif kind=='gzip':
   with gzip.GzipFile(fileobj=base) as stream:yield stream
  elif kind=='xz':
   with lzma.LZMAFile(base) as stream:yield stream
  elif kind=='bzip2':
   with bz2.BZ2File(base) as stream:yield stream
  else:
   with zipfile.ZipFile(base) as archive:
    images=[i for i in archive.infolist() if not i.is_dir() and i.filename.casefold().endswith(('.iso','.img'))]
    if len(images)!=1:raise ValueError('O ZIP deve conter exatamente uma imagem ISO ou IMG.')
    if images[0].flag_bits&1:raise ValueError('ZIP protegido por senha não é suportado.')
    with archive.open(images[0]) as stream:yield stream

def expanded_size(path,limit=None,fd=None,cancel=None):
 if image_kind(path)=='raw':size=os.fstat(fd).st_size if fd is not None else Path(path).stat().st_size
 else:
  size=0
  with image_stream(path,fd) as stream:
   while chunk:=stream.read(CHUNK_SIZE):
    if cancel:cancel()
    size+=len(chunk)
    if limit is not None and size>limit:raise ValueError('A imagem descomprimida é maior que o USB.')
 if size<=0:raise ValueError('A imagem está vazia.')
 if limit is not None and size>limit:raise ValueError('A imagem é maior que o USB.')
 return size
