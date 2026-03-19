import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import random
import requests
from bs4 import BeautifulSoup
from typing import Optional

from config.settings import SELENIUM
from core.logger import get_logger

logger = get_logger("crawler")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def random_delay():
    time.sleep(random.uniform(SELENIUM["delay_min"], SELENIUM["delay_max"]))


def _parse_price(text: str) -> Optional[int]:
    """텍스트에서 숫자만 추출해서 정수 반환"""
    cleaned = ""
    for ch in text:
        if ch.isdigit():
            cleaned += ch
    return int(cleaned) if cleaned else None


def get_aladin_min_price(isbn: str, retries: int = 3) -> Optional[int]:
    """
    알라딘 중고 최저가 크롤링
    - 1차: Ere_sub_pink 클래스 (중고 판매가 목록)
    - 2차: Ritem 클래스 (최저가 표시 영역)
    """
    url = (
        f"https://www.aladin.co.kr/shop/UsedShop/wuseditemall.aspx"
        f"?ISBN={isbn}&TabType=1"
    )

    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # 1차: Ere_sub_pink — 개인 판매자 중고 가격 목록
            prices = []
            for el in soup.select(".Ere_sub_pink"):
                text = el.get_text(strip=True)
                price = _parse_price(text)
                if price and 100 <= price <= 500000:
                    prices.append(price)

            if prices:
                min_price = min(prices)
                logger.info(
                    f"[{isbn}] 알라딘 중고 최저가: {min_price:,}원 "
                    f"({len(prices)}건 중 최저)"
                )
                return min_price

            # 2차: Ritem — 최저가 표시 영역
            for el in soup.select(".Ritem"):
                text = el.get_text(strip=True)
                if "최저가" in text:
                    price = _parse_price(text)
                    if price and 100 <= price <= 500000:
                        logger.info(f"[{isbn}] 알라딘 최저가(Ritem): {price:,}원")
                        return price

            logger.warning(f"[{isbn}] 가격 정보 없음 (시도 {attempt+1}/{retries})")
            random_delay()

        except requests.RequestException as e:
            logger.error(f"[{isbn}] 요청 오류 (시도 {attempt+1}/{retries}): {e}")
            random_delay()

    logger.warning(f"[{isbn}] 최저가 조회 실패")
    return None


def get_aladin_min_price_bulk(isbn_list: list) -> dict:
    """
    여러 ISBN 일괄 크롤링
    반환: {isbn: min_price 또는 None}
    """
    results = {}
    total = len(isbn_list)

    for idx, isbn in enumerate(isbn_list):
        logger.info(f"크롤링 중 ({idx+1}/{total}): {isbn}")
        results[isbn] = get_aladin_min_price(isbn)
        random_delay()

    success = sum(1 for v in results.values() if v is not None)
    logger.info(f"크롤링 완료: {success}/{total}건 성공")
    return results


if __name__ == "__main__":
    print("=== crawler.py 테스트 ===")

    test_cases = [
        ("채식주의자",    "9788936434267"),
        ("82년생 김지영", "9788954651135"),
    ]

    for title, isbn in test_cases:
        print(f"\n[{title}] ISBN: {isbn}")
        price = get_aladin_min_price(isbn)
        if price:
            print(f"  ✅ 알라딘 중고 최저가: {price:,}원")
        else:
            print(f"  ⚠️  조회 실패")

    print("\n=== 테스트 완료 ===")
