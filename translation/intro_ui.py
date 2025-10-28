from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QPainterPath, QPainter
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpacerItem, QSizePolicy


class TranslateIntroPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(96, 96)

        # 加载并缩放图像
        pixmap = QPixmap("ui/icon/DeepShell/icon_DeepShell_语种翻译.png").scaled(
            96, 96, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )

        # 创建圆角遮罩
        rounded = QPixmap(96, 96)
        rounded.fill(Qt.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, 96, 96, 12, 12)  # 圆角半径 = 24px
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        # 设置结果
        self.logo_label.setPixmap(rounded)
        self.logo_label.setAlignment(Qt.AlignCenter)

        # 介绍文字
        self.welcome_label = QLabel("语种翻译")
        self.welcome_label.setStyleSheet("""
                    font-family: Microsoft YaHei;
                    font-weight: 400;
                    font-size: 20px;
                    color: #FFFEFE;
                    background: transparent;
                """)
        self.welcome_label.setWordWrap(True)
        self.welcome_label.setFixedSize(QSize(200, 19))
        self.welcome_label.setAlignment(Qt.AlignCenter)

        self.intro_label = QLabel("长文短句精准译，阅读沟通无边界。语种翻译基于先进的语言模型，AI可以理解上下文语义，提供准确且自然流畅的翻译结果，满足日常交流和专业翻译需求。")
        self.intro_label.setStyleSheet("""
                    font-family: Microsoft YaHei;
                    font-weight: 400;
                    font-size: 14px;
                    color: #B3B3B3;
                    background: transparent;
                """)
        self.intro_label.setWordWrap(True)
        self.intro_label.setFixedSize(QSize(380, 64))
        self.intro_label.setAlignment(Qt.AlignLeft)

        layout = QVBoxLayout()
        layout.addItem(QSpacerItem(10, 132, QSizePolicy.Expanding, QSizePolicy.Fixed))
        layout.addWidget(self.logo_label, alignment=Qt.AlignCenter)
        layout.addItem(QSpacerItem(10, 30, QSizePolicy.Expanding, QSizePolicy.Fixed))
        layout.addWidget(self.welcome_label, alignment=Qt.AlignCenter)
        layout.addItem(QSpacerItem(10, 17, QSizePolicy.Expanding, QSizePolicy.Fixed))
        layout.addWidget(self.intro_label, alignment=Qt.AlignCenter)
        layout.addStretch()
        self.setLayout(layout)



