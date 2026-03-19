class RpaBaseException(Exception):
    """RPA 공통 기본 예외"""
    pass

class LoginFailedException(RpaBaseException):
    """플랫폼 로그인 실패"""
    pass

class ItemNotFoundException(RpaBaseException):
    """상품 검색 결과 없음"""
    pass

class InvalidDataException(RpaBaseException):
    """엑셀 데이터 유효성 오류"""
    def __init__(self, message: str, row: int = None, column: str = None):
        self.row = row
        self.column = column
        detail = f" (행: {row}, 컬럼: {column})" if row else ""
        super().__init__(f"{message}{detail}")

class PlatformException(RpaBaseException):
    """플랫폼 처리 중 오류"""
    def __init__(self, platform: str, message: str):
        self.platform = platform
        super().__init__(f"[{platform}] {message}")

class CredentialException(RpaBaseException):
    """계정 정보 오류"""
    pass
