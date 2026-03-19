import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QGridLayout, QPushButton, QLabel, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

from datetime import datetime

STYLE = """
QMainWindow, QWidget {
    background-color: #F0F4F8;
    font-family: '맑은 고딕', sans-serif;
}
QPushButton.module-btn {
    font-size: 16pt;
    font-weight: bold;
    min-height: 110px;
    border-radius: 12px;
    border: none;
    padding: 16px;
}
QLabel#title {
    font-size: 24pt;
    font-weight: bold;
    color: #1D3557;
    padding: 16px;
}
QLabel#subtitle {
    font-size: 12pt;
    color: #666666;
    padding-bottom: 10px;
}
QLabel#status {
    font-size: 11pt;
    color: #888888;
    padding: 6px;
}
"""

MODULES = [
    {
        "title":   "📚 상품등록 자동화",
        "desc":    "중앙 DB → 플랫폼별\n업로드 엑셀 자동 생성",
        "color":   "#1D6340",
        "hover":   "#155230",
        "module":  "m1",
    },
    {
        "title":   "🗑️  재고정리 자동화",
        "desc":    "판매완료 상품\n자동 품절/삭제 처리",
        "color":   "#C00000",
        "hover":   "#A00000",
        "module":  "m2",
    },
    {
        "title":   "💰 가격 모니터링",
        "desc":    "알라딘 최저가 크롤링\n가격 자동 조정 보고서",
        "color":   "#2E75B6",
        "hover":   "#1F5A9E",
        "module":  "m3",
    },
    {
        "title":   "📦 주문처리 자동화",
        "desc":    "다채널 주문 통합\n택배 송장 자동 생성",
        "color":   "#5B3A8E",
        "hover":   "#472D72",
        "module":  "m4",
    },
    {
        "title":   "🗄️  DB 관리",
        "desc":    "중앙 DB 템플릿 생성\n스키마 확인",
        "color":   "#E8860A",
        "hover":   "#C06A08",
        "module":  "m5",
    },
    {
        "title":   "⚙️  설정",
        "desc":    "플랫폼 계정 등록\nPIN 설정",
        "color":   "#546E7A",
        "hover":   "#37474F",
        "module":  "settings",
    },
]


class SettingsWindow(QMainWindow):
    """계정 등록 설정 창"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚙️  설정 — 계정 등록")
        self.setMinimumSize(500, 520)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        layout.addWidget(QLabel("플랫폼 계정 등록"))

        from PyQt5.QtWidgets import QLineEdit, QGroupBox, QHBoxLayout
        platforms = [
            ("알라딘",    "aladin"),
            ("개똥이네",  "gaddong"),
            ("북코아",    "bookcoa"),
            ("스마트스토어", "smartstore"),
        ]

        self.inputs = {}
        for label, key in platforms:
            grp = QGroupBox(label)
            grp.setStyleSheet("font-size:12pt; font-weight:bold;")
            row = QHBoxLayout(grp)
            id_input = QLineEdit()
            id_input.setPlaceholderText("아이디")
            id_input.setStyleSheet("font-size:12pt; padding:6px; min-height:36px;")
            pw_input = QLineEdit()
            pw_input.setPlaceholderText("비밀번호")
            pw_input.setEchoMode(QLineEdit.Password)
            pw_input.setStyleSheet("font-size:12pt; padding:6px; min-height:36px;")
            row.addWidget(id_input)
            row.addWidget(pw_input)
            self.inputs[key] = (id_input, pw_input)
            layout.addWidget(grp)

        pin_grp = QGroupBox("보안 PIN (4~8자리 숫자)")
        pin_grp.setStyleSheet("font-size:12pt; font-weight:bold;")
        pin_row = QHBoxLayout(pin_grp)
        self.pin_input = QLineEdit()
        self.pin_input.setPlaceholderText("PIN 입력")
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setStyleSheet("font-size:13pt; padding:8px; min-height:42px;")
        pin_row.addWidget(self.pin_input)
        layout.addWidget(pin_grp)

        btn_save = QPushButton("💾  저장")
        btn_save.setStyleSheet(
            "font-size:15pt; font-weight:bold; min-height:55px; "
            "background:#1D6340; color:white; border-radius:8px; border:none;"
        )
        btn_save.clicked.connect(self._save)
        layout.addWidget(btn_save)

    def _save(self):
        from core.security import save_credentials
        pin = self.pin_input.text().strip()
        if not pin:
            QMessageBox.warning(self, "알림", "PIN을 입력하세요.")
            return
        creds = {}
        for key, (id_inp, pw_inp) in self.inputs.items():
            uid = id_inp.text().strip()
            pw  = pw_inp.text().strip()
            if uid and pw:
                creds[key] = {"id": uid, "pw": pw}
        if not creds:
            QMessageBox.warning(self, "알림", "최소 한 개 이상의 계정을 입력하세요.")
            return
        try:
            save_credentials(pin, creds)
            QMessageBox.information(
                self, "저장 완료",
                f"✅ {len(creds)}개 계정이 암호화 저장됐습니다."
            )
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")


class MainWindow(QMainWindow):
    """RPA 메인 런처"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("📚 중고책 판매 자동화 RPA")
        self.setMinimumSize(720, 620)
        self.setStyleSheet(STYLE)
        self._init_ui()
        self.child_windows = []

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(24, 16, 24, 16)

        # 타이틀
        title = QLabel("📚 중고책 판매 자동화 RPA")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("실행할 모듈을 선택하세요")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(line)

        # 모듈 버튼 그리드 (2열)
        grid = QGridLayout()
        grid.setSpacing(14)

        for idx, mod in enumerate(MODULES):
            btn = QPushButton(f"{mod['title']}\n\n{mod['desc']}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-size: 14pt;
                    font-weight: bold;
                    min-height: 110px;
                    border-radius: 12px;
                    border: none;
                    padding: 14px;
                    background-color: {mod['color']};
                    color: white;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {mod['hover']};
                }}
                QPushButton:pressed {{
                    background-color: {mod['hover']};
                }}
            """)
            btn.clicked.connect(lambda _, m=mod["module"]: self._open_module(m))
            row, col = divmod(idx, 2)
            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(line2)

        # 상태바
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.lbl_status = QLabel(f"준비 완료  |  {now}")
        self.lbl_status.setObjectName("status")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status)

    def _open_module(self, module: str):
        try:
            win = None
            if module == "m1":
                from modules.m1_registration.gui import M1Window
                win = M1Window()
            elif module == "m2":
                from modules.m2_inventory.gui import M2Window
                win = M2Window()
            elif module == "m3":
                from modules.m3_pricing.gui import M3Window
                win = M3Window()
            elif module == "m4":
                from modules.m4_orders.gui import M4Window
                win = M4Window()
            elif module == "m5":
                from modules.m5_db_design.schema import create_master_template
                path = create_master_template()
                QMessageBox.information(
                    self, "DB 템플릿 생성",
                    f"✅ 템플릿이 생성됐습니다:\n{path}"
                )
                return
            elif module == "settings":
                win = SettingsWindow()

            if win:
                win.show()
                self.child_windows.append(win)
                self.lbl_status.setText(f"{module.upper()} 모듈 실행 중  |  {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"모듈 실행 실패:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("맑은 고딕", 11))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
