# services/direct.py
import hmac
import hashlib
import base64
from datetime import datetime, timedelta

from config import DEEP_LINK_SECRET
from utils.time import now_ts

# Срок жизни токена - 7 дней
TOKEN_TTL_SECONDS = 7 * 24 * 3600

def generate_token(task_id: int) -> str:
    """Генерирует безопасный токен для deeplink."""
    exp = now_ts() + TOKEN_TTL_SECONDS
    message = f"{task_id}:{exp}".encode('utf-8')
    secret = DEEP_LINK_SECRET.encode('utf-8')
    
    # Создаем подпись
    signature = hmac.new(secret, message, hashlib.sha256).digest()
    
    # Кодируем в URL-safe формат
    token_parts = [
        base64.urlsafe_b64encode(signature).decode('utf-8').rstrip('='),
        str(task_id),
        str(exp)
    ]
    return ".".join(token_parts)

def validate_token(token: str) -> int | None:
    """
    Проверяет токен.
    Возвращает task_id, если токен валиден и не истек, иначе None.
    """
    try:
        signature_b64, task_id_str, exp_str = token.split('.')
        task_id = int(task_id_str)
        exp = int(exp_str)
        
        # 1. Проверка срока годности
        if exp < now_ts():
            return None
            
        # 2. Пересоздание подписи для проверки
        message = f"{task_id}:{exp}".encode('utf-8')
        secret = DEEP_LINK_SECRET.encode('utf-8')
        expected_signature = hmac.new(secret, message, hashlib.sha256).digest()
        
        # Декодируем подпись из токена
        padding = '=' * (-len(signature_b64) % 4)
        decoded_signature = base64.urlsafe_b64decode(signature_b64 + padding)
        
        # 3. Сравнение подписей
        if hmac.compare_digest(decoded_signature, expected_signature):
            return task_id
        else:
            return None
            
    except Exception:
        return None
