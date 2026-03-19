import os
import json
import base64
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet


CREDENTIALS_PATH = Path(__file__).parent.parent / "config" / "credentials.enc"
SALT_PATH = Path(__file__).parent.parent / "config" / "salt.bin"


def _derive_key(pin: str, salt: bytes) -> bytes:
    """PIN으로부터 Fernet 암호화 키 파생"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(pin.encode()))


def _get_or_create_salt() -> bytes:
    """salt 파일 읽기 또는 신규 생성"""
    if SALT_PATH.exists():
        return SALT_PATH.read_bytes()
    salt = os.urandom(16)
    SALT_PATH.write_bytes(salt)
    return salt


def save_credentials(pin: str, credentials: dict) -> None:
    """
    플랫폼 계정 정보를 암호화하여 저장
    credentials 예시:
    {
        "aladin": {"id": "user@email.com", "pw": "password123"},
        "smartstore": {"id": "user", "pw": "pass"}
    }
    """
    salt = _get_or_create_salt()
    key = _derive_key(pin, salt)
    f = Fernet(key)
    encrypted = f.encrypt(json.dumps(credentials).encode())
    CREDENTIALS_PATH.write_bytes(encrypted)
    print("계정 정보가 안전하게 저장되었습니다.")


def load_credentials(pin: str) -> dict:
    """
    암호화된 계정 정보 복호화 후 반환
    PIN이 틀리면 예외 발생
    """
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError("저장된 계정 정보가 없습니다. 먼저 설정에서 계정을 등록하세요.")
    salt = _get_or_create_salt()
    key = _derive_key(pin, salt)
    f = Fernet(key)
    try:
        decrypted = f.decrypt(CREDENTIALS_PATH.read_bytes())
        return json.loads(decrypted.decode())
    except Exception:
        raise ValueError("PIN이 올바르지 않거나 계정 파일이 손상되었습니다.")


def get_platform_credential(pin: str, platform: str) -> dict:
    """특정 플랫폼의 계정 정보만 반환"""
    creds = load_credentials(pin)
    if platform not in creds:
        raise KeyError(f"'{platform}' 플랫폼의 계정 정보가 없습니다.")
    return creds[platform]


def credentials_exist() -> bool:
    """저장된 계정 파일 존재 여부 확인"""
    return CREDENTIALS_PATH.exists()


if __name__ == "__main__":
    # 동작 테스트
    test_pin = "1234"
    test_creds = {
        "aladin": {"id": "test@aladin.co.kr", "pw": "aladin_pass"},
        "smartstore": {"id": "mystore", "pw": "store_pass"},
    }

    print("=== security.py 테스트 ===")
    save_credentials(test_pin, test_creds)

    loaded = load_credentials(test_pin)
    print(f"복호화 성공: {list(loaded.keys())}")

    aladin = get_platform_credential(test_pin, "aladin")
    print(f"알라딘 계정 ID: {aladin['id']}")

    try:
        load_credentials("wrong_pin")
    except ValueError as e:
        print(f"잘못된 PIN 테스트 통과: {e}")

    print("=== 모든 테스트 통과 ===")
