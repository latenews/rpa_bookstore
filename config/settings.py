from pathlib import Path

# 프로젝트 루트 경로
BASE_DIR = Path(__file__).parent.parent

# 디렉토리 경로
CONFIG_DIR  = BASE_DIR / "config"
LOGS_DIR    = BASE_DIR / "logs"
OUTPUT_DIR  = BASE_DIR / "output"
ASSETS_DIR  = BASE_DIR / "assets"
TEMPLATE_DIR = ASSETS_DIR / "templates"

# 중앙 DB 엑셀 파일 경로 (사용자가 지정)
MASTER_DB_PATH = BASE_DIR / "assets" / "master_db.xlsx"

# Selenium 설정
SELENIUM = {
    "headless": True,          # VPS에서는 True 필수
    "page_load_timeout": 30,   # 초
    "implicit_wait": 5,        # 초
    "retry_count": 3,          # 실패 시 재시도 횟수
    "delay_min": 1.5,          # 요청 간 최소 딜레이 (초)
    "delay_max": 3.0,          # 요청 간 최대 딜레이 (초)
}

# 가격 조정 기본 설정
PRICING = {
    "undercut_amount": 100,    # 최저가 대비 차감 금액 (원)
    "min_gap": 50,             # 이 금액 이하 차이면 미조정 (원)
    "min_allowed_price": 500,  # 절대 최저 허용 판매가 (원)
}

# 플랫폼 목록
PLATFORMS = ["smartstore", "aladin", "yes24", "gaddong", "bookcoa"]

# 중앙 DB 컬럼 정의
DB_COLUMNS = {
    "상품ID":          "product_id",
    "ISBN":            "isbn",
    "도서명":          "title",
    "도서명_조합":     "title_combined",
    "저자":            "author",
    "출판사":          "publisher",
    "정가":            "original_price",
    "판매가":          "sale_price",
    "최저허용가":      "min_price",
    "상태등급":        "condition",
    "재고수량":        "stock",
    "등록대상_스마트": "reg_smartstore",
    "등록대상_알라딘": "reg_aladin",
    "등록대상_예스24": "reg_yes24",
    "알라딘_상품코드": "aladin_code",
    "개똥이네_상품코드":"gaddong_code",
    "북코아_상품코드": "bookcoa_code",
    "판매완료여부":    "is_sold",
    "판매채널":        "sold_channel",
    "처리상태":        "process_status",
}
