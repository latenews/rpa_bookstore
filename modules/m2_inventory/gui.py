import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QCheckBox,
    QGroupBox, QProgressBar, QMessageBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import pandas as pd
from pathlib import Path
from datetime import datetime

from config.settings import OUTPUT_DIR
from core.db_manager import DBManager
from core.security import load_credentials, credentials_exist
from core.logger import get_logger
from modules.m2_inventory.selenium_handler import get_handler

logger = get_logger("m2_gui")

STYLE = """
QMainWindow, QWidget { background-color: #F5F5F5; font-family: '맑은 고딕', sans-serif; }
QPushButton {
    font-size: 16pt; font-weight: bold;
    min-height: 60px; border-radius: 8px;
    padding: 8px 20px; border: none;
}
QPushButton#btn_run {
    background-color: #C00000; color: white;
}
QPushButton#btn_run:hover { background-color: #A00000; }
QPushButton#btn_run:disabled { background-color: #AAAAAA; }
QPushButton#btn_file {
    background-color: #2E75B6; color: white;
    font-size: 14pt; min-height: 50px;
}
QPushButton#btn_file:hover { background-color: #1F5A9E; }
QPushButton#btn_confirm {
    background-color: #E8860A; color: white;
    font-size: 13pt; min-height: 45px;
}
QLabel#title { font-size: 20pt; font-weight: bold; color: #1D3557; padding: 10px; }
QLabel { font-size: 13pt; color: #333333; }
QTextEdit {
    font-size: 11pt; background-color: #1E1E1E;
    color: #D4D4D4; border-radius: 6px; padding: 8px;
    font-family: 'Consolas', monospace;
}
QCheckBox { font-size: 14pt; spacing: 10px; }
QCheckBox::indicator { width: 22px; height: 22px; }
QRadioButton { font-size: 14pt; spacing: 10px; }
QRadioButton::indicator { width: 22px; height: 22px; }
QGroupBox {
    font-size: 13pt; font-weight: bold;
    border: 2px solid #CCCCCC; border-radius: 8px;
    margin-top: 10px; padding-top: 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar {
    height: 20px; border-radius: 8px;
    font-size: 11pt; text-align: center;
}
QProgressBar::chunk { background-color: #C00000; border-radius: 8px; }
"""


class InventoryWorker(QThread):
    """재고정리 백그라운드 작업 스레드"""
    log_signal   = pyqtSignal(str)
    progress     = pyqtSignal(int)
    finished     = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, items: list, platforms: list, action: str, pin: str):
        super().__init__()
        self.items     = items
        self.platforms = platforms
        self.action    = action
        self.pin       = pin

    def run(self):
        try:
            # 계정 정보 로드
            creds = load_credentials(self.pin)
            total_platforms = len(self.platforms)

            for p_idx, platform in enumerate(self.platforms):
                self.log_signal.emit(f"\n🔄 [{platform}] 작업 시작 ({len(self.items)}건)...")

                if platform not in creds:
                    self.log_signal.emit(f"  ⚠️  [{platform}] 계정 정보 없음, 건너뜀")
                    continue

                cred = creds[platform]
                handler = get_handler(platform)

                try:
                    self.log_signal.emit(f"  🔑 [{platform}] 로그인 중...")
                    handler.start()
                    handler.login(cred["id"], cred["pw"])
                    self.log_signal.emit(f"  ✅ [{platform}] 로그인 성공")

                    total_items = len(self.items)
                    for i_idx, item in enumerate(self.items):
                        keyword = (
                            item.get(f"{platform}_상품코드") or
                            item.get("도서명", "")
                        )
                        item_id = item.get("상품ID", keyword)
                        self.log_signal.emit(f"  처리중 ({i_idx+1}/{total_items}): {keyword}")

                        try:
                            ok = handler.process_item(keyword, self.action)
                            if ok:
                                self.log_signal.emit(f"    ✅ 완료: {keyword}")
                            else:
                                self.log_signal.emit(f"    ⏭️  스킵: {keyword} (상품 없음)")
                        except Exception as e:
                            self.log_signal.emit(f"    ❌ 실패: {keyword} — {e}")

                        pct = int(((p_idx * total_items + i_idx + 1) /
                                   (total_platforms * total_items)) * 100)
                        self.progress.emit(pct)

                finally:
                    handler.quit()
                    self.log_signal.emit(f"  🔒 [{platform}] 브라우저 종료")

            summary = f"작업 완료 | {self.action} | 총 {len(self.items)}건"
            self.finished.emit(summary)

        except Exception as e:
            self.error_signal.emit(str(e))


class M2Window(QMainWindow):
    """모듈 2 — 재고정리 자동화 메인 창"""

    def __init__(self):
        super().__init__()
        self.db_path  = None
        self.items_df = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("🗑️  재고정리 자동화 — 모듈 2")
        self.setMinimumSize(800, 750)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # 타이틀
        title = QLabel("🗑️  재고정리 자동화")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(line)

        # 경고 문구
        warn = QLabel("⚠️  주의: 실제 플랫폼에서 상품이 품절/삭제됩니다. 신중하게 실행하세요.")
        warn.setStyleSheet(
            "color: #C00000; font-size: 12pt; font-weight: bold; "
            "background: #FFF0F0; padding: 8px; border-radius: 6px;"
        )
        warn.setAlignment(Qt.AlignCenter)
        layout.addWidget(warn)

        # DB 파일 선택
        file_group = QGroupBox("1단계: 중앙 DB 파일 선택")
        file_layout = QVBoxLayout(file_group)
        self.lbl_file = QLabel("파일을 선택하지 않았습니다.")
        self.lbl_file.setStyleSheet("color: #888888; font-size: 12pt;")
        btn_file = QPushButton("📂  중앙 DB 엑셀 파일 열기")
        btn_file.setObjectName("btn_file")
        btn_file.clicked.connect(self._select_file)
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #C00000; font-size: 12pt; font-weight: bold;")
        file_layout.addWidget(self.lbl_file)
        file_layout.addWidget(btn_file)
        file_layout.addWidget(self.lbl_count)
        layout.addWidget(file_group)

        # 플랫폼 선택
        platform_group = QGroupBox("2단계: 처리할 플랫폼 선택")
        platform_layout = QHBoxLayout(platform_group)
        self.chk_aladin  = QCheckBox("알라딘")
        self.chk_gaddong = QCheckBox("개똥이네")
        self.chk_bookcoa = QCheckBox("북코아")
        self.chk_aladin.setChecked(True)
        for chk in [self.chk_aladin, self.chk_gaddong, self.chk_bookcoa]:
            platform_layout.addWidget(chk)
        layout.addWidget(platform_group)

        # 처리 방식 선택
        action_group = QGroupBox("3단계: 처리 방식 선택")
        action_layout = QHBoxLayout(action_group)
        self.radio_soldout = QRadioButton("품절 처리  (판매 중지, 복구 가능)")
        self.radio_delete  = QRadioButton("삭제 처리  (완전 삭제, 복구 불가)")
        self.radio_soldout.setChecked(True)
        self.radio_delete.setStyleSheet("color: #C00000;")
        self.btn_grp = QButtonGroup()
        self.btn_grp.addButton(self.radio_soldout)
        self.btn_grp.addButton(self.radio_delete)
        action_layout.addWidget(self.radio_soldout)
        action_layout.addWidget(self.radio_delete)
        layout.addWidget(action_group)

        # PIN 입력
        pin_group = QGroupBox("4단계: 보안 PIN 입력")
        pin_layout = QHBoxLayout(pin_group)
        pin_lbl = QLabel("PIN:")
        from PyQt5.QtWidgets import QLineEdit
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("설정에서 등록한 PIN 번호 입력")
        self.pin_input.setStyleSheet(
            "font-size: 14pt; padding: 8px; border: 2px solid #CCCCCC; border-radius: 6px;"
        )
        self.pin_input.setMinimumHeight(48)
        pin_layout.addWidget(pin_lbl)
        pin_layout.addWidget(self.pin_input)
        layout.addWidget(pin_group)

        # 실행 버튼
        self.btn_run = QPushButton("▶  재고정리 실행")
        self.btn_run.setObjectName("btn_run")
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self._run)
        layout.addWidget(self.btn_run)

        # 진행률
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # 로그창
        log_group = QGroupBox("진행 상황")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(160)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "중앙 DB 파일 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        self.db_path = Path(path)
        self.lbl_file.setText(f"✅  {self.db_path.name}")
        self.lbl_file.setStyleSheet("color: #1D6340; font-size: 12pt; font-weight: bold;")

        db = DBManager(self.db_path)
        self.items_df = db.load_sold_items()
        count = len(self.items_df)
        self.lbl_count.setText(f"재고정리 대상: {count}건")
        self._log(f"DB 로드: {count}건 처리 대상")
        self.btn_run.setEnabled(count > 0)

    def _get_platforms(self) -> list:
        platforms = []
        if self.chk_aladin.isChecked():  platforms.append("aladin")
        if self.chk_gaddong.isChecked(): platforms.append("gaddong")
        if self.chk_bookcoa.isChecked(): platforms.append("bookcoa")
        return platforms

    def _run(self):
        platforms = self._get_platforms()
        if not platforms:
            QMessageBox.warning(self, "알림", "플랫폼을 하나 이상 선택하세요.")
            return

        pin = self.pin_input.text().strip()
        if not pin:
            QMessageBox.warning(self, "알림", "PIN을 입력하세요.")
            return

        action = "soldout" if self.radio_soldout.isChecked() else "delete"
        action_kr = "품절 처리" if action == "soldout" else "삭제 처리"
        count = len(self.items_df)

        # 삭제 처리 시 추가 경고
        if action == "delete":
            reply = QMessageBox.warning(
                self, "⚠️  삭제 확인",
                f"정말로 {count}건을 완전 삭제하시겠습니까?\n\n삭제 후 복구할 수 없습니다!",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        reply = QMessageBox.question(
            self, "최종 확인",
            f"플랫폼: {', '.join(platforms)}\n"
            f"처리방식: {action_kr}\n"
            f"대상: {count}건\n\n실행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        items = self.items_df.to_dict("records")

        self.worker = InventoryWorker(items, platforms, action, pin)
        self.worker.log_signal.connect(self._log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, summary: str):
        self.btn_run.setEnabled(True)
        self.progress.setValue(100)
        QMessageBox.information(self, "완료", f"✅ {summary}")

    def _on_error(self, msg: str):
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "오류", f"❌ 오류:\n{msg}")
        self._log(f"❌ 오류: {msg}")

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {msg}")
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )


def run_gui():
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 11))
    win = M2Window()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    print("=== gui.py 문법 검사 ===")
    try:
        import ast
        with open(__file__, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print("✅ 문법 오류 없음")
        print("✅ 모듈 2 GUI 완성")
        print("   주요 기능:")
        print("   - 품절/삭제 처리 방식 선택")
        print("   - PIN 입력 → 계정 자동 복호화")
        print("   - 삭제 시 2단계 확인 다이얼로그")
        print("   - 백그라운드 스레드 처리")
    except SyntaxError as e:
        print(f"❌ 문법 오류: {e}")
