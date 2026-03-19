import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from pathlib import Path
from openpyxl import load_workbook, Workbook

from config.settings import MASTER_DB_PATH, DB_COLUMNS
from core.logger import get_logger
from core.exceptions import InvalidDataException

logger = get_logger("db_manager")

REQUIRED_COLUMNS = ["ISBN", "도서명", "판매가", "상태등급", "재고수량"]


class DBManager:
    """중앙 DB 엑셀 읽기/쓰기 관리자"""

    def __init__(self, db_path: Path = MASTER_DB_PATH):
        self.db_path = db_path

    def load_all(self) -> pd.DataFrame:
        """전체 데이터 로드"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"중앙 DB 파일이 없습니다: {self.db_path}")
        df = pd.read_excel(self.db_path, dtype=str)
        df = df.fillna("")
        logger.info(f"DB 로드 완료: {len(df)}건 ({self.db_path.name})")
        return df

    def load_for_registration(self, platform: str) -> pd.DataFrame:
        """모듈 1용 — 등록 대상(Y) 필터링"""
        col_map = {
            "smartstore": "등록대상_스마트",
            "aladin":     "등록대상_알라딘",
            "yes24":      "등록대상_예스24",
        }
        if platform not in col_map:
            raise ValueError(f"지원하지 않는 플랫폼: {platform}")
        df = self.load_all()
        col = col_map[platform]
        if col not in df.columns:
            raise InvalidDataException(f"컬럼 없음: {col}", column=col)
        filtered = df[df[col].str.upper() == "Y"].copy()
        logger.info(f"[{platform}] 등록 대상: {len(filtered)}건")
        return filtered

    def load_sold_items(self) -> pd.DataFrame:
        """모듈 2용 — 판매완료(Y) 미처리 항목"""
        df = self.load_all()
        mask = (
            (df["판매완료여부"].str.upper() == "Y") &
            (df["처리상태"] != "완료")
        )
        result = df[mask].copy()
        logger.info(f"재고정리 대상: {len(result)}건")
        return result

    def load_for_pricing(self) -> pd.DataFrame:
        """모듈 3용 — 알라딘 등록 + 판매중인 상품"""
        df = self.load_all()
        mask = (
            (df["등록대상_알라딘"].str.upper() == "Y") &
            (df["판매완료여부"].str.upper() != "Y")
        )
        result = df[mask].copy()
        logger.info(f"가격 모니터링 대상: {len(result)}건")
        return result

    def validate(self, df: pd.DataFrame) -> list:
        """필수값 누락 검사 — 오류 목록 반환"""
        errors = []
        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                errors.append({"row": 0, "column": col, "message": f"필수 컬럼 없음: {col}"})
                continue
            empty_rows = df[df[col].str.strip() == ""].index.tolist()
            for row in empty_rows:
                errors.append({
                    "row": row + 2,
                    "column": col,
                    "message": "필수값 누락"
                })
        if errors:
            logger.warning(f"유효성 오류 {len(errors)}건 발견")
        else:
            logger.info("유효성 검사 통과")
        return errors

    def update_status(self, product_id: str, status: str) -> None:
        """처리상태 업데이트"""
        if not self.db_path.exists():
            return
        df = pd.read_excel(self.db_path, dtype=str).fillna("")
        mask = df["상품ID"] == product_id
        if mask.sum() == 0:
            logger.warning(f"상품ID 없음: {product_id}")
            return
        df.loc[mask, "처리상태"] = status
        df.to_excel(self.db_path, index=False)
        logger.info(f"상태 업데이트: {product_id} → {status}")

    def create_sample_db(self) -> None:
        """샘플 중앙 DB 파일 생성"""
        sample = pd.DataFrame([
            {
                "상품ID": "P001", "ISBN": "9788936434267",
                "도서명": "채식주의자", "도서명_조합": "채식주의자",
                "저자": "한강", "출판사": "창비",
                "정가": "11000", "판매가": "6000", "최저허용가": "3000",
                "상태등급": "상", "재고수량": "1",
                "등록대상_스마트": "Y", "등록대상_알라딘": "Y", "등록대상_예스24": "N",
                "알라딘_상품코드": "", "개똥이네_상품코드": "", "북코아_상품코드": "",
                "판매완료여부": "N", "판매채널": "", "처리상태": "미처리",
            },
            {
                "상품ID": "P002", "ISBN": "9788954651135",
                "도서명": "82년생 김지영", "도서명_조합": "82년생 김지영",
                "저자": "조남주", "출판사": "민음사",
                "정가": "14000", "판매가": "8000", "최저허용가": "4000",
                "상태등급": "최상", "재고수량": "1",
                "등록대상_스마트": "Y", "등록대상_알라딘": "Y", "등록대상_예스24": "Y",
                "알라딘_상품코드": "ALI-12345", "개똥이네_상품코드": "", "북코아_상품코드": "",
                "판매완료여부": "Y", "판매채널": "알라딘", "처리상태": "미처리",
            },
        ])
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        sample.to_excel(self.db_path, index=False)
        logger.info(f"샘플 DB 생성: {self.db_path}")


if __name__ == "__main__":
    db = DBManager()

    print("=== db_manager.py 테스트 ===")
    db.create_sample_db()

    df_all = db.load_all()
    print(f"전체 로드: {len(df_all)}건")

    df_aladin = db.load_for_registration("aladin")
    print(f"알라딘 등록 대상: {len(df_aladin)}건")

    df_sold = db.load_sold_items()
    print(f"재고정리 대상: {len(df_sold)}건")

    errors = db.validate(df_all)
    print(f"유효성 오류: {len(errors)}건")

    print("=== 모든 테스트 통과 ===")
