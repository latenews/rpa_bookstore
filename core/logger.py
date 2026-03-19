import logging
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(module_name: str) -> logging.Logger:
    """
    모듈별 로거 반환
    - 콘솔 출력 + 날짜별 파일 저장
    """
    logger = logging.getLogger(module_name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 콘솔 핸들러
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    # 파일 핸들러 (날짜별)
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"{today}_{module_name}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


class ProcessLogger:
    """
    모듈 2(재고정리) 등 대량 처리용 결과 로거
    성공/실패/스킵 건수 집계
    """
    def __init__(self, module_name: str):
        self.logger = get_logger(module_name)
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def log_success(self, item_id: str, message: str = ""):
        self.success += 1
        self.logger.info(f"✅ 성공 | {item_id} {message}")

    def log_fail(self, item_id: str, message: str = ""):
        self.failed += 1
        self.errors.append((item_id, message))
        self.logger.error(f"❌ 실패 | {item_id} {message}")

    def log_skip(self, item_id: str, message: str = ""):
        self.skipped += 1
        self.logger.warning(f"⏭️ 스킵 | {item_id} {message}")

    def summary(self) -> str:
        total = self.success + self.failed + self.skipped
        result = (
            f"\n{'='*40}\n"
            f"처리 완료 | 전체: {total}건\n"
            f"  ✅ 성공: {self.success}건\n"
            f"  ❌ 실패: {self.failed}건\n"
            f"  ⏭️ 스킵: {self.skipped}건\n"
            f"{'='*40}"
        )
        self.logger.info(result)
        return result
