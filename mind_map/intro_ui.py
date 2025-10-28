from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QPainter, QPainterPath
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpacerItem, QSizePolicy


class MindMapIntroPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # logo
        self.logo_label = QLabel()
        self.logo_label.setFixedSize(96, 96)

        # 加载并缩放图像
        pixmap = QPixmap("ui/icon/DeepShell/icon_DeepShell_思维导图.png").scaled(
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
        self.welcome_label = QLabel("思维导图")
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

        self.intro_label = QLabel("AI生成思维导图功能可以快速将复杂的信息进行结构化梳理，基于强大的语言理解能力，自动识别信息之间的逻辑关系，构建出层次分明、逻辑清晰的思维导图。")
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



