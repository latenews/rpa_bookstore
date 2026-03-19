import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from pathlib import Path
from datetime import datetime

from core.logger import get_logger

logger = get_logger("order_merger")

PLATFORM_ORDER_MAPPING = {
    "smartstore": {
        "주문번호":     "order_id",
        "주문일시":     "order_date",
        "수취인명":     "receiver_name",
        "수취인연락처": "receiver_phone",
        "배송지주소":   "address",
        "상품명":       "product_name",
        "수량":         "quantity",
        "주문금액":     "amount",
        "배송메모":     "memo",
    },
    "aladin": {
        "주문ID":       "order_id",
        "주문일":       "order_date",
        "받는분":       "receiver_name",
        "전화번호":     "receiver_phone",
        "주소":         "address",
        "도서명":       "product_name",
        "수량":         "quantity",
        "결제금액":     "amount",
        "배송요청사항": "memo",
    },
    "yes24": {
        "주문번호":     "order_id",
        "결제일시":     "order_date",
        "수령인":       "receiver_name",
        "수령인연락처": "receiver_phone",
        "배송주소":     "address",
        "상품명":       "product_name",
        "수량":         "quantity",
        "판매금액":     "amount",
        "배송메모":     "memo",
    },
    "gaddong": {
        "주문번호":     "order_id",
        "주문날짜":     "order_date",
        "받는사람":     "receiver_name",
        "연락처":       "receiver_phone",
        "주소":         "address",
        "상품명":       "product_name",
        "수량":         "quantity",
        "금액":         "amount",
        "메모":         "memo",
    },
}

STANDARD_COLUMNS = [
    "order_id", "platform", "order_date",
    "receiver_name", "receiver_phone", "address",
    "product_name", "quantity", "amount",
    "memo", "invoice_no", "courier", "status",
]


def normalize_order(df, platform):
    if platform not in PLATFORM_ORDER_MAPPING:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")
    mapping = PLATFORM_ORDER_MAPPING[platform]
    result = pd.DataFrame()
    for src_col, std_col in mapping.items():
        if src_col in df.columns:
            result[std_col] = df[src_col].astype(str).str.strip()
        else:
            result[std_col] = ""
            logger.warning(f"[{platform}] 컬럼 없음: {src_col}")
    result["platform"]   = platform
    result["invoice_no"] = ""
    result["courier"]    = ""
    result["status"]     = "미처리"
    for col in STANDARD_COLUMNS:
        if col not in result.columns:
            result[col] = ""
    logger.info(f"[{platform}] 주문 정규화: {len(result)}건")
    return result[STANDARD_COLUMNS]


def merge_orders(file_list):
    dfs = []
    for item in file_list:
        path     = Path(item["path"])
        platform = item["platform"]
        if not path.exists():
            logger.warning(f"파일 없음: {path}")
            continue
        try:
            df = pd.read_excel(path, dtype=str).fillna("")
            normalized = normalize_order(df, platform)
            dfs.append(normalized)
            logger.info(f"[{platform}] 로드: {len(df)}건 ({path.name})")
        except Exception as e:
            logger.error(f"[{platform}] 로드 실패: {e}")
    if not dfs:
        logger.warning("처리할 주문 파일이 없습니다")
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    merged = pd.concat(dfs, ignore_index=True)
    merged = merged.drop_duplicates(subset=["order_id", "platform"])
    logger.info(f"통합 완료: 전체 {len(merged)}건")
    return merged


def create_sample_order_files(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    files = []
    ss_df = pd.DataFrame([{
        "주문번호": "SS-20260319-001", "주문일시": "2026-03-19 09:00",
        "수취인명": "홍길동", "수취인연락처": "010-1234-5678",
        "배송지주소": "서울시 강남구 테헤란로 123",
        "상품명": "채식주의자", "수량": "1", "주문금액": "6000", "배송메모": "문앞 부탁",
    }])
    ss_path = output_dir / "smartstore_orders.xlsx"
    ss_df.to_excel(ss_path, index=False)
    files.append({"path": ss_path, "platform": "smartstore"})

    al_df = pd.DataFrame([{
        "주문ID": "AL-20260319-001", "주문일": "2026-03-19",
        "받는분": "김철수", "전화번호": "010-9876-5432",
        "주소": "부산시 해운대구 해운대로 456",
        "도서명": "82년생 김지영", "수량": "1", "결제금액": "8000", "배송요청사항": "",
    }])
    al_path = output_dir / "aladin_orders.xlsx"
    al_df.to_excel(al_path, index=False)
    files.append({"path": al_path, "platform": "aladin"})
    return files


if __name__ == "__main__":
    from config.settings import OUTPUT_DIR
    print("=== order_merger.py 테스트 ===")
    sample_dir = OUTPUT_DIR / "sample_orders"
    file_list = create_sample_order_files(sample_dir)
    print(f"샘플 파일 생성: {len(file_list)}개")
    merged = merge_orders(file_list)
    print(f"통합 결과: {len(merged)}건")
    print(merged[["order_id","platform","receiver_name","product_name","amount"]].to_string(index=False))
    print("=== 테스트 완료 ===")
