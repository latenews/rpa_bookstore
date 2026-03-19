import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QCheckBox,
    QGroupBox, QProgressBar, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

import pandas as pd
from pathlib import Path
from datetime import datetime

from config.settings import OUTPUT_DIR
from core.db_manager import DBManager
from core.logger import get_logger
from modules.m1_registration.excel_builder import build_upload_excel

logger = get_logger("m1_gui")

# ── 공통 스타일 (50~60대 사용자 고려: 큰 글씨, 명확한 색상) ──
STYLE = """
QMainWindow, QWidget {
    background-color: #F5F5F5;
    font-family: '맑은 고딕', sans-serif;
}
QPushButton {
    font-size: 16pt;
    font-weight: bold;
    min-height: 60px;
    border-radius: 8px;
    padding: 8px 20px;
    border: none;
}
QPushButton#btn_run {
    background-color: #1D6340;
    color: white;
}
QPushButton#btn_run:hover { background-color: #155230; }
QPushButton#btn_run:disabled { background-color: #AAAAAA; }
QPushButton#btn_file {
    background-color: #2E75B6;
    color: white;
    font-size: 14pt;
    min-height: 50px;
}
QPushButton#btn_file:hover { background-color: #1F5A9E; }
QPushButton#btn_open {
    background-color: #E8860A;
    color: white;
    font-size: 13pt;
    min-height: 45px;
}
QLabel#title {
    font-size: 20pt;
    font-weight: bold;
    color: #1D3557;
    padding: 10px;
}
QLabel {
    font-size: 13pt;
    color: #333333;
}
QTextEdit {
    font-size: 11pt;
    background-color: #1E1E1E;
    color: #D4D4D4;
    border-radius: 6px;
    padding: 8px;
    font-family: 'Consolas', monospace;
}
QCheckBox {
    font-size: 14pt;
    spacing: 10px;
}
QCheckBox::indicator { width: 22px; height: 22px; }
QGroupBox {
    font-size: 13pt;
    font-weight: bold;
    border: 2px solid #CCCCCC;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar {
    height: 20px;
    border-radius: 8px;
    font-size: 11pt;
    text-align: center;
}
QProgressBar::chunk { background-color: #1D6340; border-radius: 8px; }
"""


class WorkerThread(QThread):
    """백그라운드 작업 스레드 — GUI 멈춤 방지"""
    log_signal    = pyqtSignal(str)
    progress      = pyqtSignal(int)
    finished      = pyqtSignal(dict)
    error_signal  = pyqtSignal(str)

    def __init__(self, db_path: Path, platforms: list):
        super().__init__()
        self.db_path   = db_path
        self.platforms = platforms

    def run(self):
        try:
            self.log_signal.emit("📂 중앙 DB 파일 읽는 중...")
            db = DBManager(self.db_path)
            df = db.load_all()
            self.log_signal.emit(f"✅ DB 로드 완료: 전체 {len(df)}건")

            errors = db.validate(df)
            if errors:
                for e in errors:
                    self.log_signal.emit(f"⚠️  유효성 오류 - {e['column']} ({e['row']}행): {e['message']}")
                self.log_signal.emit(f"\n오류 {len(errors)}건이 있습니다. 확인 후 다시 실행하세요.")
                self.error_signal.emit(f"유효성 오류 {len(errors)}건 발견")
                return

            results = {}
            total = len(self.platforms)

            for idx, platform in enumerate(self.platforms):
                self.log_signal.emit(f"\n🔄 [{platform}] 처리 중...")
                col_map = {
                    "smartstore": "등록대상_스마트",
                    "aladin":     "등록대상_알라딘",
                    "yes24":      "등록대상_예스24",
                }
                col = col_map.get(platform, "")
                if col and col in df.columns:
                    target = df[df[col].str.upper() == "Y"].copy()
                else:
                    target = df.copy()

                if target.empty:
                    self.log_signal.emit(f"  ⏭️  [{platform}] 등록 대상 없음, 건너뜀")
                    self.progress.emit(int((idx + 1) / total * 100))
                    continue

                path = build_upload_excel(target, platform)
                results[platform] = path
                self.log_signal.emit(f"  ✅ [{platform}] {path.name} ({len(target)}건)")
                self.progress.emit(int((idx + 1) / total * 100))

            self.log_signal.emit(f"\n🎉 완료! {len(results)}개 파일 생성")
            self.finished.emit(results)

        except Exception as e:
            self.error_signal.emit(str(e))


class M1Window(QMainWindow):
    """모듈 1 — 상품등록 자동화 메인 창"""

    def __init__(self):
        super().__init__()
        self.db_path = None
        self.result_paths = {}
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("📚 상품등록 자동화 — 모듈 1")
        self.setMinimumSize(780, 680)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 16, 20, 16)

        # 타이틀
        title = QLabel("📚 상품등록 자동화")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(line)

        # DB 파일 선택
        file_group = QGroupBox("1단계: 중앙 DB 파일 선택")
        file_layout = QVBoxLayout(file_group)
        self.lbl_file = QLabel("파일을 선택하지 않았습니다.")
        self.lbl_file.setStyleSheet("color: #888888; font-size: 12pt;")
        self.lbl_file.setWordWrap(True)
        btn_file = QPushButton("📂  중앙 DB 엑셀 파일 열기")
        btn_file.setObjectName("btn_file")
        btn_file.clicked.connect(self._select_file)
        file_layout.addWidget(self.lbl_file)
        file_layout.addWidget(btn_file)
        layout.addWidget(file_group)

        # 플랫폼 선택
        platform_group = QGroupBox("2단계: 등록할 플랫폼 선택")
        platform_layout = QHBoxLayout(platform_group)
        self.chk_smartstore = QCheckBox("스마트스토어")
        self.chk_aladin     = QCheckBox("알라딘")
        self.chk_yes24      = QCheckBox("예스24")
        for chk in [self.chk_smartstore, self.chk_aladin, self.chk_yes24]:
            chk.setChecked(True)
            platform_layout.addWidget(chk)
        layout.addWidget(platform_group)

        # 실행 버튼
        self.btn_run = QPushButton("▶  업로드 파일 생성 시작")
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
        self.log_view.setMinimumHeight(180)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

        # 결과 열기 버튼
        self.btn_open = QPushButton("📁  생성된 파일 폴더 열기")
        self.btn_open.setObjectName("btn_open")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_output)
        layout.addWidget(self.btn_open)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "중앙 DB 파일 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if path:
            self.db_path = Path(path)
            self.lbl_file.setText(f"✅  {self.db_path.name}")
            self.lbl_file.setStyleSheet("color: #1D6340; font-size: 12pt; font-weight: bold;")
            self.btn_run.setEnabled(True)
            self._log(f"파일 선택: {path}")

    def _get_selected_platforms(self) -> list:
        platforms = []
        if self.chk_smartstore.isChecked(): platforms.append("smartstore")
        if self.chk_aladin.isChecked():     platforms.append("aladin")
        if self.chk_yes24.isChecked():      platforms.append("yes24")
        return platforms

    def _run(self):
        platforms = self._get_selected_platforms()
        if not platforms:
            QMessageBox.warning(self, "알림", "플랫폼을 하나 이상 선택하세요.")
            return

        reply = QMessageBox.question(
            self, "확인",
            f"선택한 플랫폼: {', '.join(platforms)}\n\n업로드 파일을 생성하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.log_view.clear()
        self._log("작업을 시작합니다...")

        self.worker = WorkerThread(self.db_path, platforms)
        self.worker.log_signal.connect(self._log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, results: dict):
        self.result_paths = results
        self.btn_run.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.progress.setValue(100)
        QMessageBox.information(
            self, "완료",
            f"✅ 파일 생성 완료!\n\n{len(results)}개 플랫폼 파일이 output 폴더에 저장됐습니다."
        )

    def _on_error(self, msg: str):
        self.btn_run.setEnabled(True)
        QMessageBox.critical(self, "오류 발생", f"❌ 오류:\n{msg}")
        self._log(f"❌ 오류: {msg}")

    def _open_output(self):
        import subprocess
        path = str(OUTPUT_DIR)
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {msg}")
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )


def run_gui():
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 11))
    win = M1Window()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # VPS에서는 GUI 없이 문법 검사만
    print("=== gui.py 문법 검사 ===")
    try:
        import ast
        with open(__file__, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print("✅ 문법 오류 없음")
        print("✅ 모듈 1 GUI 코드 완성")
        print("   (실제 실행은 Windows exe 패키징 후 가능)")
    except SyntaxError as e:
        print(f"❌ 문법 오류: {e}")
