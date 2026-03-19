import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import random
from abc import ABC, abstractmethod
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

from config.settings import SELENIUM, LOGS_DIR
from core.logger import get_logger, ProcessLogger
from core.exceptions import LoginFailedException, ItemNotFoundException, PlatformException
from modules.m2_inventory import platform_selectors as selectors

logger = get_logger("selenium_handler")


def get_driver(headless: bool = None) -> webdriver.Chrome:
    """Chrome WebDriver 생성"""
    options = Options()
    is_headless = SELENIUM["headless"] if headless is None else headless
    if is_headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=ko_KR")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(SELENIUM["page_load_timeout"])
    driver.implicitly_wait(SELENIUM["implicit_wait"])
    logger.info("ChromeDriver 시작 완료")
    return driver


def random_delay(min_sec: float = None, max_sec: float = None):
    """요청 간 랜덤 딜레이 (차단 방지)"""
    lo = min_sec or SELENIUM["delay_min"]
    hi = max_sec or SELENIUM["delay_max"]
    time.sleep(random.uniform(lo, hi))


def take_screenshot(driver: webdriver.Chrome, name: str) -> Path:
    """실패 시 스크린샷 저장"""
    LOGS_DIR.mkdir(exist_ok=True)
    path = LOGS_DIR / f"screenshot_{name}_{int(time.time())}.png"
    try:
        driver.save_screenshot(str(path))
        logger.info(f"스크린샷 저장: {path.name}")
    except Exception:
        pass
    return path


# ──────────────────────────────────────────
# 기반 클래스
# ──────────────────────────────────────────
class BaseHandler(ABC):
    """모든 플랫폼 핸들러의 공통 기반"""

    def __init__(self, platform: str):
        self.platform = platform
        self.driver: webdriver.Chrome = None
        self.process_log = ProcessLogger(f"m2_{platform}")

    def start(self):
        self.driver = get_driver()

    def quit(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def wait_for(self, css_selector: str, timeout: int = 10):
        """요소가 나타날 때까지 대기"""
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )

    def click(self, css_selector: str, timeout: int = 10):
        """요소 클릭 (클릭 가능할 때까지 대기)"""
        el = WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector))
        )
        el.click()
        return el

    def safe_find(self, css_selector: str):
        """요소 찾기 — 없으면 None 반환"""
        try:
            return self.driver.find_element(By.CSS_SELECTOR, css_selector)
        except NoSuchElementException:
            return None

    @abstractmethod
    def login(self, user_id: str, password: str): ...

    @abstractmethod
    def process_item(self, keyword: str, action: str = "soldout") -> bool: ...

    def process_items(self, items: list, action: str = "soldout") -> dict:
        """
        여러 상품 일괄 처리
        items: [{"상품ID": ..., "도서명": ..., "알라딘_상품코드": ...}, ...]
        action: "soldout" | "delete"
        반환: ProcessLogger summary
        """
        for item in items:
            keyword = item.get(f"{self.platform}_상품코드") or item.get("도서명", "")
            item_id = item.get("상품ID", keyword)
            try:
                success = self.process_item(keyword, action)
                if success:
                    self.process_log.log_success(item_id, f"{action} 처리 완료")
                else:
                    self.process_log.log_skip(item_id, "상품 없음 또는 이미 처리됨")
            except PlatformException as e:
                self.process_log.log_fail(item_id, str(e))
                take_screenshot(self.driver, f"{self.platform}_{item_id}")
            except Exception as e:
                self.process_log.log_fail(item_id, f"예외: {e}")
                take_screenshot(self.driver, f"{self.platform}_error")
            random_delay()

        return self.process_log.summary()


# ──────────────────────────────────────────
# 알라딘 핸들러
# ──────────────────────────────────────────
class AladinHandler(BaseHandler):

    LOGIN_URL = "https://www.aladin.co.kr/common/ualadin/login.aspx"
    GOODS_URL = "https://www.aladin.co.kr/mystore/UsedShopMyGoods.aspx"
    SEL = selectors.ALADIN

    def __init__(self):
        super().__init__("aladin")

    def login(self, user_id: str, password: str):
        logger.info("[알라딘] 로그인 시도")
        self.driver.get(self.LOGIN_URL)
        random_delay(1, 2)

        try:
            self.wait_for(self.SEL["login_id"]).send_keys(user_id)
            self.driver.find_element(By.CSS_SELECTOR, self.SEL["login_pw"]).send_keys(password)
            self.click(self.SEL["login_btn"])
            random_delay(2, 3)

            # 로그인 성공 확인
            try:
                self.wait_for(self.SEL["login_check"], timeout=8)
                logger.info("[알라딘] 로그인 성공")
            except TimeoutException:
                take_screenshot(self.driver, "aladin_login_fail")
                raise LoginFailedException("알라딘 로그인 실패 — ID/PW 확인 또는 캡챠 발생")
        except LoginFailedException:
            raise
        except Exception as e:
            raise LoginFailedException(f"알라딘 로그인 오류: {e}")

    def process_item(self, keyword: str, action: str = "soldout") -> bool:
        """상품 검색 후 품절/삭제 처리"""
        if not keyword.strip():
            return False

        logger.info(f"[알라딘] 처리 시작: {keyword} ({action})")
        self.driver.get(self.GOODS_URL)
        random_delay(1, 2)

        try:
            search_input = self.wait_for(self.SEL["search_input"])
            search_input.clear()
            search_input.send_keys(keyword)
            self.click(self.SEL["search_btn"])
            random_delay(1.5, 2.5)

            # 검색 결과 확인
            results = self.driver.find_elements(By.CSS_SELECTOR, self.SEL["search_result"])
            if not results:
                logger.warning(f"[알라딘] 검색 결과 없음: {keyword}")
                return False

            # 첫 번째 결과 체크박스 선택
            checkbox = self.safe_find(self.SEL["item_checkbox"])
            if checkbox:
                checkbox.click()
                random_delay(0.5, 1)

            # 품절 또는 삭제 처리
            btn_sel = self.SEL["soldout_btn"] if action == "soldout" else self.SEL["delete_btn"]
            btn = self.safe_find(btn_sel)
            if not btn:
                logger.warning(f"[알라딘] {action} 버튼 없음")
                return False

            btn.click()
            random_delay(0.5, 1)

            # 확인 팝업 처리
            confirm = self.safe_find(self.SEL["confirm_ok"])
            if confirm:
                confirm.click()
                random_delay(1, 2)

            logger.info(f"[알라딘] {action} 완료: {keyword}")
            return True

        except TimeoutException:
            raise PlatformException("aladin", f"페이지 로딩 타임아웃: {keyword}")
        except Exception as e:
            raise PlatformException("aladin", f"처리 오류: {e}")


# ──────────────────────────────────────────
# 개똥이네 핸들러 (골격)
# ──────────────────────────────────────────
class GaddongHandler(BaseHandler):

    SEL = selectors.GADDONG

    def __init__(self):
        super().__init__("gaddong")

    def login(self, user_id: str, password: str):
        logger.info("[개똥이네] 로그인 시도")
        self.driver.get(self.SEL["login_url"])
        random_delay(1, 2)
        try:
            self.wait_for(self.SEL["login_id"]).send_keys(user_id)
            self.driver.find_element(By.CSS_SELECTOR, self.SEL["login_pw"]).send_keys(password)
            self.click(self.SEL["login_btn"])
            random_delay(2, 3)
            self.wait_for(self.SEL["login_check"], timeout=8)
            logger.info("[개똥이네] 로그인 성공")
        except TimeoutException:
            take_screenshot(self.driver, "gaddong_login_fail")
            raise LoginFailedException("개똥이네 로그인 실패")

    def process_item(self, keyword: str, action: str = "soldout") -> bool:
        logger.info(f"[개똥이네] 처리 시작: {keyword} ({action})")
        self.driver.get(self.SEL["goods_url"])
        random_delay(1, 2)
        try:
            self.wait_for(self.SEL["search_input"]).send_keys(keyword)
            self.click(self.SEL["search_btn"])
            random_delay(1.5, 2)
            results = self.driver.find_elements(By.CSS_SELECTOR, self.SEL["search_result"])
            if not results:
                return False
            btn_sel = self.SEL["soldout_btn"] if action == "soldout" else self.SEL["delete_btn"]
            btn = self.safe_find(btn_sel)
            if not btn:
                return False
            btn.click()
            random_delay(0.5, 1)
            confirm = self.safe_find(self.SEL["confirm_ok"])
            if confirm:
                confirm.click()
                random_delay(1, 2)
            return True
        except Exception as e:
            raise PlatformException("gaddong", f"처리 오류: {e}")


# ──────────────────────────────────────────
# 북코아 핸들러 (골격)
# ──────────────────────────────────────────
class BookcoaHandler(BaseHandler):

    SEL = selectors.BOOKCOA

    def __init__(self):
        super().__init__("bookcoa")

    def login(self, user_id: str, password: str):
        logger.info("[북코아] 로그인 시도")
        self.driver.get(self.SEL["login_url"])
        random_delay(1, 2)
        try:
            self.wait_for(self.SEL["login_id"]).send_keys(user_id)
            self.driver.find_element(By.CSS_SELECTOR, self.SEL["login_pw"]).send_keys(password)
            self.click(self.SEL["login_btn"])
            random_delay(2, 3)
            self.wait_for(self.SEL["login_check"], timeout=8)
            logger.info("[북코아] 로그인 성공")
        except TimeoutException:
            take_screenshot(self.driver, "bookcoa_login_fail")
            raise LoginFailedException("북코아 로그인 실패")

    def process_item(self, keyword: str, action: str = "soldout") -> bool:
        logger.info(f"[북코아] 처리 시작: {keyword} ({action})")
        self.driver.get(self.SEL["goods_url"])
        random_delay(1, 2)
        try:
            self.wait_for(self.SEL["search_input"]).send_keys(keyword)
            self.click(self.SEL["search_btn"])
            random_delay(1.5, 2)
            results = self.driver.find_elements(By.CSS_SELECTOR, self.SEL["search_result"])
            if not results:
                return False
            btn_sel = self.SEL["soldout_btn"] if action == "soldout" else self.SEL["delete_btn"]
            btn = self.safe_find(btn_sel)
            if not btn:
                return False
            btn.click()
            random_delay(0.5, 1)
            confirm = self.safe_find(self.SEL["confirm_ok"])
            if confirm:
                confirm.click()
                random_delay(1, 2)
            return True
        except Exception as e:
            raise PlatformException("bookcoa", f"처리 오류: {e}")


# ──────────────────────────────────────────
# 핸들러 팩토리
# ──────────────────────────────────────────
def get_handler(platform: str) -> BaseHandler:
    handlers = {
        "aladin":   AladinHandler,
        "gaddong":  GaddongHandler,
        "bookcoa":  BookcoaHandler,
    }
    if platform not in handlers:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")
    return handlers[platform]()


if __name__ == "__main__":
    print("=== selenium_handler.py 문법 검사 ===")
    try:
        import ast
        with open(__file__, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print("✅ 문법 오류 없음")
        print("✅ 핸들러 클래스 구조:")
        print("   BaseHandler    — 공통 기반")
        print("   AladinHandler  — 알라딘 (완성)")
        print("   GaddongHandler — 개똥이네 (골격)")
        print("   BookcoaHandler — 북코아 (골격)")
        print("   get_handler()  — 팩토리 함수")
    except SyntaxError as e:
        print(f"❌ 문법 오류: {e}")
