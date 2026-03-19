import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from core.logger import get_logger
from core.exceptions import InvalidDataException

logger = get_logger("mapper")

# 상태등급 변환 규칙
CONDITION_MAP = {
    "smartstore": {"최상": "중고-최상", "상": "중고-상",  "중": "중고-중",  "하": "중고-하"},
    "aladin":     {"최상": "최상",       "상": "상",       "중": "중",       "하": "하"},
    "yes24":      {"최상": "S",          "상": "A",        "중": "B",        "하": "C"},
}

# 플랫폼별 컬럼 매핑 정의
# key: 업로드 엑셀 컬럼명, value: 변환 함수 또는 DB 컬럼명
PLATFORM_MAPPING = {

    "smartstore": {
        "상품명":       lambda r: r.get("도서명_조합") or r.get("도서명", ""),
        "판매가":       lambda r: r.get("판매가", ""),
        "재고수량":     lambda r: r.get("재고수량", "1"),
        "상품상태":     lambda r: CONDITION_MAP["smartstore"].get(r.get("상태등급",""), "중고-상"),
        "모델명":       lambda r: r.get("ISBN", ""),
        "브랜드":       lambda r: r.get("출판사", ""),
        "제조사":       lambda r: r.get("출판사", ""),
        "과세여부":     lambda r: "면세",
        "배송방법":     lambda r: "택배",
    },

    "aladin": {
        "ISBN":         lambda r: r.get("ISBN", ""),
        "제목":         lambda r: r.get("도서명_조합") or r.get("도서명", ""),
        "저자":         lambda r: r.get("저자", ""),
        "출판사":       lambda r: r.get("출판사", ""),
        "판매가":       lambda r: r.get("판매가", ""),
        "상태":         lambda r: CONDITION_MAP["aladin"].get(r.get("상태등급",""), "상"),
        "재고":         lambda r: r.get("재고수량", "1"),
    },

    "yes24": {
        "ISBN":         lambda r: r.get("ISBN", ""),
        "도서명":       lambda r: r.get("도서명_조합") or r.get("도서명", ""),
        "저자명":       lambda r: r.get("저자", ""),
        "출판사명":     lambda r: r.get("출판사", ""),
        "판매금액":     lambda r: r.get("판매가", ""),
        "상품상태":     lambda r: CONDITION_MAP["yes24"].get(r.get("상태등급",""), "A"),
        "수량":         lambda r: r.get("재고수량", "1"),
    },
}


def build_title_combined(row: dict) -> str:
    """
    도서명_조합 자동 생성
    예: '채식주의자 1~3권 세트' 또는 그냥 '채식주의자'
    도서명_조합이 이미 있으면 그대로 사용
    """
    if row.get("도서명_조합", "").strip():
        return row["도서명_조합"].strip()
    return row.get("도서명", "").strip()


def map_to_platform(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """
    중앙 DB DataFrame → 플랫폼별 업로드용 DataFrame 변환
    """
    if platform not in PLATFORM_MAPPING:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")

    mapping = PLATFORM_MAPPING[platform]
    rows = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        # 도서명_조합 자동 보완
        row_dict["도서명_조합"] = build_title_combined(row_dict)

        mapped_row = {}
        for col_name, transform in mapping.items():
            try:
                mapped_row[col_name] = transform(row_dict)
            except Exception as e:
                logger.warning(f"매핑 오류 [{platform}] {col_name}: {e}")
                mapped_row[col_name] = ""

        rows.append(mapped_row)

    result = pd.DataFrame(rows)
    logger.info(f"[{platform}] 매핑 완료: {len(result)}건 / {len(result.columns)}개 컬럼")
    return result


def validate_mapped(df: pd.DataFrame, platform: str) -> list:
    """매핑 결과 필수값 검증"""
    required = {
        "smartstore": ["상품명", "판매가"],
        "aladin":     ["ISBN", "제목", "판매가"],
        "yes24":      ["ISBN", "도서명", "판매금액"],
    }
    errors = []
    for col in required.get(platform, []):
        if col not in df.columns:
            errors.append(f"필수 컬럼 없음: {col}")
            continue
        empty = df[df[col].astype(str).str.strip() == ""]
        if not empty.empty:
            errors.append(f"[{col}] {len(empty)}건 값 없음 (행: {list(empty.index + 2)})")
    return errors


if __name__ == "__main__":
    sample_df = pd.DataFrame([
        {
            "상품ID": "P001", "ISBN": "9788936434267",
            "도서명": "채식주의자", "도서명_조합": "",
            "저자": "한강", "출판사": "창비",
            "판매가": "6000", "상태등급": "상", "재고수량": "1",
        },
        {
            "상품ID": "P002", "ISBN": "9788954651135",
            "도서명": "82년생 김지영", "도서명_조합": "82년생 김지영",
            "저자": "조남주", "출판사": "민음사",
            "판매가": "8000", "상태등급": "최상", "재고수량": "1",
        },
    ])

    print("=== mapper.py 테스트 ===")
    for platform in ["smartstore", "aladin", "yes24"]:
        mapped = map_to_platform(sample_df, platform)
        errors = validate_mapped(mapped, platform)
        print(f"[{platform}] 컬럼: {list(mapped.columns)}")
        print(f"[{platform}] 오류: {errors if errors else '없음'}")
        print()
    print("=== 테스트 완료 ===")
