from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem, QSizePolicy
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QMovie, QPixmap, QFont
from config.config_manager import ConfigManager

class ChatIntroPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setObjectName('guide_widget')
        self.setStyleSheet("""
            background: transparent;
            border-radius: 12px;
        """)

        # Logo
        self.movie_label = QLabel()
        self.movie_label.setPixmap(QPixmap("ui/icon/DeepShell/shell.png").scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.movie_label.setStyleSheet("""
            background: transparent;
            border-radius: 24px;
        """)
        self.movie_label.setFixedSize(QSize(96, 96))
        self.movie_label.setAlignment(Qt.AlignCenter)

        self.logo_text = QLabel("DeepShell")
        self.logo_text.setAlignment(Qt.AlignCenter)
        font = QFont("Microsoft YaHei", 20)
        font.setWeight(QFont.Bold)
        self.logo_text.setFont(font)
        self.logo_text.setStyleSheet("""
            QLabel{
                color: #FFFFFF;
                background: transparent;
                padding: 0px;
                margin-top: 8px;   /* 与 Logo 的间距 */
            }
            text-shadow: 1px 1px 4px rgba(0,0,0,180);
        """)

        # 导航页布局 - 只显示Logo
        layout = QVBoxLayout()
        layout.addStretch()
        layout.addWidget(self.movie_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.logo_text, alignment=Qt.AlignCenter)
        layout.addStretch()
        self.setLayout(layout)


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = ChatIntroPage()
    window.show()
    sys.exit(app.exec_())