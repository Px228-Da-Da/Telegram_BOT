import hashlib
from urllib.parse import urlparse

def normalize_url(url: str) -> str:
    """
    Приводим URL к нормализованному виду для антидублей:
    - убираем якорь (#...)
    - обрезаем лишние /
    - регистр домена не чувствителен
    """
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip('/')
    return f"{parsed.scheme}://{netloc}{path}"

def dedupe_hash(url: str) -> str:
    normalized = normalize_url(url)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()
