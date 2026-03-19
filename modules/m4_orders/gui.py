import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTextEdit, QGroupBox,
    QProgressBar, QMessageBox, QFrame, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

import pandas as pd
from pathlib import Path
from datetime import datetime

from config.settings import OUTPUT_DIR
from core.logger import get_logger
from modules.m4_orders.order_merger import merge_orders
from modules.m4_orders.invoice_handler import (
    build_invoice_excel, update_invoice_numbers, export_merged_orders
)

logger = get_logger("m4_gui")

STYLE = """
QMainWindow, QWidget { background-color: #F5F5F5; font-family: '맑은 고딕', sans-serif; }
QPushButton {
    font-size: 15pt; font-weight: bold;
    min-height: 55px; border-radius: 8px;
    padding: 8px 16px; border: none;
}
QPushButton#btn_add    { background-color: #2E75B6; color: white; font-size: 13pt; min-height: 45px; }
QPushButton#btn_add:hover { background-color: #1F5A9E; }
QPushButton#btn_merge  { background-color: #1D6340; color: white; }
QPushButton#btn_merge:hover { background-color: #155230; }
QPushButton#btn_merge:disabled { background-color: #AAAAAA; }
QPushButton#btn_invoice { background-color: #E8860A; color: white; }
QPushButton#btn_invoice:hover { background-color: #C06A08; }
QPushButton#btn_invoice:disabled { background-color: #AAAAAA; }
QPushButton#btn_export { background-color: #5B3A8E; color: white; font-size: 13pt; min-height: 45px; }
QLabel#title { font-size: 20pt; font-weight: bold; color: #1D3557; padding: 10px; }
QLabel { font-size: 12pt; color: #333333; }
QTextEdit {
    font-size: 10pt; background-color: #1E1E1E;
    color: #D4D4D4; border-radius: 6px; padding: 8px;
    font-family: 'Consolas', monospace;
}
QGroupBox {
    font-size: 12pt; font-weight: bold;
    border: 2px solid #CCCCCC; border-radius: 8px;
    margin-top: 10px; padding-top: 10px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar { height: 18px; border-radius: 6px; font-size: 10pt; text-align: center; }
QProgressBar::chunk { background-color: #1D6340; border-radius: 6px; }
QComboBox { font-size: 12pt; padding: 6px; min-height: 38px; border: 2px solid #CCCCCC; border-radius: 6px; }
QTableWidget { font-size: 11pt; gridline-color: #DDDDDD; }
QTableWidget::item { padding: 4px; }
QHeaderView::section { background-color: #2E75B6; color: white; font-size: 11pt; font-weight: bold; padding: 6px; }
"""


class MergeWorker(QThread):
    log_signal   = pyqtSignal(str)
    progress     = pyqtSignal(int)
    finished     = pyqtSignal(object)
    error_signal = pyqtSignal(str)

    def __init__(self, file_list):
        super().__init__()
        self.file_list = file_list

    def run(self):
        try:
            self.log_signal.emit(f"📦 {len(self.file_list)}개 파일 통합 중...")
            self.progress.emit(30)
            merged = merge_orders(self.file_list)
            self.progress.emit(100)
            self.log_signal.emit(f"✅ 통합 완료: {len(merged)}건")
            self.finished.emit(merged)
        except Exception as e:
            self.error_signal.emit(str(e))


class M4Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.file_list  = []
        self.merged_df  = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("📦 주문처리 자동화 — 모듈 4")
        self.setMinimumSize(860, 780)
        self.setStyleSheet(STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 14, 20, 14)

        title = QLabel("📦 주문처리 자동화")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(line)

        # 파일 추가
        file_group = QGroupBox("1단계: 플랫폼별 주문 파일 추가")
        file_layout = QVBoxLayout(file_group)

        add_row = QHBoxLayout()
        self.combo_platform = QComboBox()
        self.combo_platform.addItems(["smartstore", "aladin", "yes24", "gaddong"])
        add_row.addWidget(QLabel("플랫폼:"))
        add_row.addWidget(self.combo_platform)
        btn_add = QPushButton("➕  파일 추가")
        btn_add.setObjectName("btn_add")
        btn_add.clicked.connect(self._add_file)
        add_row.addWidget(btn_add)
        file_layout.addLayout(add_row)

        self.file_table = QTableWidget(0, 3)
        self.file_table.setHorizontalHeaderLabels(["플랫폼", "파일명", "삭제"])
        self.file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.file_table.setMaximumHeight(130)
        file_layout.addWidget(self.file_table)
        layout.addWidget(file_group)

        # 통합 실행
        self.btn_merge = QPushButton("🔗  주문 파일 통합")
        self.btn_merge.setObjectName("btn_merge")
        self.btn_merge.setEnabled(False)
        self.btn_merge.clicked.connect(self._run_merge)
        layout.addWidget(self.btn_merge)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # 통합 결과 미리보기
        preview_group = QGroupBox("통합 주문 미리보기")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget(0, 6)
        self.preview_table.setHorizontalHeaderLabels(
            ["주문번호", "플랫폼", "수취인", "상품명", "금액", "상태"]
        )
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.preview_table.setMaximumHeight(160)
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)

        # 송장 출력
        invoice_group = QGroupBox("2단계: 택배사 선택 및 송장 출력")
        invoice_layout = QHBoxLayout(invoice_group)
        invoice_layout.addWidget(QLabel("택배사:"))
        self.combo_courier = QComboBox()
        self.combo_courier.addItems(["CJ대한통운", "한진택배", "우체국택배"])
        invoice_layout.addWidget(self.combo_courier)
        self.btn_invoice = QPushButton("🖨️  송장 파일 생성")
        self.btn_invoice.setObjectName("btn_invoice")
        self.btn_invoice.setEnabled(False)
        self.btn_invoice.clicked.connect(self._make_invoice)
        invoice_layout.addWidget(self.btn_invoice)
        layout.addWidget(invoice_group)

        # 통합 현황 저장
        self.btn_export = QPushButton("💾  통합 주문 현황 저장")
        self.btn_export.setObjectName("btn_export")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self._export)
        layout.addWidget(self.btn_export)

        # 로그
        log_group = QGroupBox("진행 상황")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

    def _add_file(self):
        platform = self.combo_platform.currentText()
        path, _ = QFileDialog.getOpenFileName(
            self, f"{platform} 주문 파일 선택", "", "Excel Files (*.xlsx *.xls)"
        )
        if not path:
            return
        self.file_list.append({"path": path, "platform": platform})
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        self.file_table.setItem(row, 0, QTableWidgetItem(platform))
        self.file_table.setItem(row, 1, QTableWidgetItem(Path(path).name))
        del_btn = QPushButton("삭제")
        del_btn.setStyleSheet("font-size:10pt; min-height:28px; background:#E74C3C; color:white; border-radius:4px;")
        del_btn.clicked.connect(lambda _, r=row: self._remove_file(r))
        self.file_table.setCellWidget(row, 2, del_btn)
        self.btn_merge.setEnabled(True)
        self._log(f"추가: [{platform}] {Path(path).name}")

    def _remove_file(self, row):
        if row < len(self.file_list):
            self.file_list.pop(row)
        self.file_table.removeRow(row)
        if not self.file_list:
            self.btn_merge.setEnabled(False)

    def _run_merge(self):
        self.btn_merge.setEnabled(False)
        self.progress.setValue(0)
        self.worker = MergeWorker(self.file_list)
        self.worker.log_signal.connect(self._log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self._on_merged)
        self.worker.error_signal.connect(self._on_error)
        self.worker.start()

    def _on_merged(self, merged_df):
        self.merged_df = merged_df
        self.btn_merge.setEnabled(True)
        self.btn_invoice.setEnabled(True)
        self.btn_export.setEnabled(True)

        # 미리보기 테이블 채우기
        self.preview_table.setRowCount(0)
        cols = ["order_id", "platform", "receiver_name", "product_name", "amount", "status"]
        for _, row in merged_df.iterrows():
            r = self.preview_table.rowCount()
            self.preview_table.insertRow(r)
            for c, col in enumerate(cols):
                self.preview_table.setItem(r, c, QTableWidgetItem(str(row.get(col, ""))))

        QMessageBox.information(self, "완료", f"✅ 주문 통합 완료: {len(merged_df)}건")

    def _make_invoice(self):
        courier = self.combo_courier.currentText()
        try:
            path = build_invoice_excel(self.merged_df, courier)
            self._log(f"✅ 송장 생성: {path.name}")
            QMessageBox.information(self, "완료", f"✅ [{courier}] 송장 파일 생성 완료!")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"❌ {e}")

    def _export(self):
        try:
            path = export_merged_orders(self.merged_df)
            self._log(f"✅ 통합 현황 저장: {path.name}")
            QMessageBox.information(self, "완료", f"✅ 통합 주문 현황 저장 완료!")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"❌ {e}")

    def _on_error(self, msg):
        self.btn_merge.setEnabled(True)
        QMessageBox.critical(self, "오류", f"❌ {msg}")
        self._log(f"❌ 오류: {msg}")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {msg}")
        self.log_view.verticalScrollBar().setValue(
            self.log_view.verticalScrollBar().maximum()
        )


def run_gui():
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 11))
    win = M4Window()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    print("=== gui.py 문법 검사 ===")
    try:
        import ast
        with open(__file__, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        print("✅ 문법 오류 없음")
        print("✅ 모듈 4 GUI 완성")
        print("   주요 기능:")
        print("   - 플랫폼별 파일 추가/삭제 테이블")
        print("   - 통합 결과 미리보기 테이블")
        print("   - 택배사 선택 후 송장 생성")
        print("   - 통합 주문 현황 저장")
    except SyntaxError as e:
        print(f"❌ 문법 오류: {e}")
