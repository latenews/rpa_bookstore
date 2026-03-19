import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QGroupBox,
    QProgressBar, QMessageBox, QFrame, QSpinBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import pandas as pd
from pathlib import Path
from datetime import datetime

from config.settings import OUTPUT_DIR, PRICING
from core.db_manager import DBManager
from core.logger import get_logger
from modules.m3_pricing.price_calculator import run_price_analysis, export_price_report

logger = get_logger("m3_gui")

STYLE = """
QMainWindow, QWidget { background-color: #F5F5F5; font-family: '맑은 고딕', sans-serif; }
QPushButton {
    font-size: 16pt; font-weight: bold;
    min-height: 60px; border-radius: 8px;
    padding: 8px 20px; border: none;
}
QPushButton#btn_analyze {
    background-color: #2E75B6; color: white;
}
QPushButton#btn_analyze:hover { background-color: #1F5A9E; }
QPushButton#btn_analyze:disabled { background-color: #AAAAAA; }
QPushButton#btn_file {
    background-color: #5B9BD5; color: white;
    font-size: 14pt; min-height: 50px;
}
QPushButton#btn_open {
    background-color: #1D6340; color: white;
    font-size: 13pt; min-height: 45px;
}
QLabel#title { font-size: 20pt; font-weight: bold; color: #1D3557; padding: 10px; }
QLabel { font-size: 13pt; color: #333333; }
QTextEdit {
    font-size: 11pt; background-color: #1E1E1E;
    color: #D4D4D4; border-radius: 6px; padding: 8px;
    font-family: 'Consolas', monospace;
}
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
QProgressBar::chunk { background-color: #2E75B6; border-radius: 8px; }
QSpinBox {
    font-size: 13pt; padding: 6px;
    border: 2px solid #CCCCCC; border-radius: 6px;
    min-height: 40px; min-width: 100px;
}
"""


class PriceWorker(QThread):
    """가격 분석 백그라운드 스레드"""
    log_signal   = pyqtSignal(str)
    progress     = pyqtSignal(int)
    finished     = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame, undercut: int, min_gap: int):
        super().__init__()
        self.df      = df
        self.undercut = undercut
        self.min_gap  = min_gap

    def run(self):
        try:
            import modules.m3_pricing.price_calculator as pc
            # 설정값 동적 적용
            PRICING["undercut_amount"] = self.undercut
            PRICING["min_gap"]         = self.min_gap

            self.log_signal.emit(f"📊 분석 시작: {len(self.df)}건")
            self.log_signal.emit(f"   설정 — 차감: {self.undercut:,}원 / 최소차이: {self.min_gap:,}원")
            self.progress.emit(10)

            result_df = run_price_analysis(self.df)
            self.progress.emit(80)

            adj = (result_df["조정여부"] == "Y").sum()
            self.log_signal.emit(f"✅ 분석 완료: 전체 {len(result_df)}건 / 조정대상 {adj}건")

            path = export_price_report(result_df)
            self.progress.emit(100)
            self.log_signal.emit(f"📁 보고서 저장: {path.name}")
            self.finished.emit(str(path))

        except Exception as e:
            self.error_signal.emit(str(e))


class M3Window(QMainWindow):
    """모듈 3 — 가격 모니터링 메인 창"""

    def __init__(self):
        super().__init__()
        self.db_path  = None
        self.items_df = None
        self.report_path = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("💰 가격 모니터링 — 모듈 3")
        self.setMinimumSize(780, 700)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        # 타이틀
        title = QLabel("💰 가격 모니터링 및 최저가 조정")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(line)

        # DB 파일 선택
        file_group = QGroupBox("1단계: 중앙 DB 파일 선택")
        file_layout = QVBoxLayout(file_group)
        self.lbl_file = QLabel("파일을 선택하지 않았습니다.")
        self.lbl_file.setStyleSheet("color: #888888; font-size: 12pt;")
        btn_file = QPushButton("📂  중앙 DB 엑셀 파일 열기")
        btn_file.setObjectName("btn_file")
        btn_file.clicked.connect(self._select_file)
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet("color: #2E75B6; font-size: 12pt; font-weight: bold;")
        file_layout.addWidget(self.lbl_file)
        file_layout.addWidget(btn_file)
        file_layout.addWidget(self.lbl_count)
        layout.addWidget(file_group)

        # 가격 설정
        setting_group = QGroupBox("2단계: 가격 조정 설정")
        setting_layout = QHBoxLayout(setting_group)

        setting_layout.addWidget(QLabel("경쟁 최저가 대비 차감액:"))
        self.spin_undercut = QSpinBox()
        self.spin_undercut.setRange(0, 10000)
        self.spin_undercut.setSingleStep(100)
        self.spin_undercut.setValue(PRICING["undercut_amount"])
        self.spin_undercut.setSuffix(" 원")
        setting_layout.addWidget(self.spin_undercut)

        setting_layout.addSpacing(20)
        setting_layout.addWidget(QLabel("최소 조정 기준 차이:"))
        self.spin_gap = QSpinBox()
        self.spin_gap.setRange(0, 5000)
        self.spin_gap.setSingleStep(50)
        self.spin_gap.setValue(PRICING["min_gap"])
        self.spin_gap.setSuffix(" 원")
        setting_layout.addWidget(self.spin_gap)
        setting_layout.addStretch()
        layout.addWidget(setting_group)

        # 실행 버튼
        self.btn_analyze = QPushButton("🔍  가격 분석 및 보고서 생성")
        self.btn_analyze.setObjectName("btn_analyze")
        self.btn_analyze.setEnabled(False)
        self.btn_analyze.clicked.connect(self._run)
        layout.addWidget(self.btn_analyze)

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

        # 보고서 열기
        self.btn_open = QPushButton("📁  생성된 보고서 열기")
        self.btn_open.setObjectName("btn_open")
        self.btn_open.setEnabled(False)
        self.btn_open.clicked.connect(self._open_report)
        layout.addWidget(self.btn_open)

    def _select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "중앙 DB 파일 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        self.db_path = Path(path)
        self.lbl_file.setText(f"✅  {self.db_path.name}")
        self.lbl_file.setStyleSheet(
            "color: #1D6340; font-size: 12pt; font-weight: bold;"
        )
        db = DBManager(self.db_path)
        self.items_df = db.load_for_pricing()
        count = len(self.items_df)
        self.lbl_count.setText(f"가격 모니터링 대상: {count}건")
        self._log(f"DB 로드: {count}건")
        self.btn_analyze.setEnabled(count > 0)

    def _run(self):
        reply = QMessageBox.question(
            self, "확인",
            f"알라딘 중고 최저가를 크롤링하고\n가격 비교 보고서를 생성하시겠습니까?\n\n"
            f"대상: {len(self.items_df)}건",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.btn_analyze.setEnabled(False)
        self.progress.setValue(0)

        self.worker = PriceWorker(
            self.items_df,
            self.spin_undercut.value(),
            self.spin_gap.value()
        )
        self.worker.log_signal.connect(self._log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self._on_finished)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, path: str):
        self.report_path = path
        self.btn_analyze.setEnabled(True)
        self.btn_open.setEnabled(True)
        QMessageBox.information(
            self, "완료",
            "✅ 가격 분석 완료!\n\noutput 폴더에 보고서가 저장됐습니다."
        )

    def _on_error(self, msg: str):
        self.btn_analyze.setEnabled(True)
        QMessageBox.critical(self, "오류", f"❌ 오류:\n{msg}")
        self._log(f"❌ 오류: {msg}")

    def _open_report(self):
        import subprocess
        if self.report_path:
            if sys.platform == "win32":
                os.startfile(self.report_path)
            else:
                subprocess.Popen(["xdg-open", self.report_path])

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {msg}")
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )


def run_gui():
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 11))
    win = M3Window()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    print("=== gui.py 문법 검사 ===")
    try:
        import ast
        with open(__file__, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print("✅ 문법 오류 없음")
        print("✅ 모듈 3 GUI 완성")
        print("   주요 기능:")
        print("   - 차감액 / 최소차이 스핀박스로 조정 가능")
        print("   - 알라딘 크롤링 → 가격 분석 → 보고서 생성")
        print("   - 백그라운드 스레드 처리")
    except SyntaxError as e:
        print(f"❌ 문법 오류: {e}")
