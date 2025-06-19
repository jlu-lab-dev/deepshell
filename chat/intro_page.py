from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSpacerItem, QSizePolicy
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QMovie, QPixmap
from config.config_manager import ConfigManager

class ChatIntroPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setObjectName('guide_widget')
        self.setStyleSheet("""
            background: rgba(17,27,35,0.8);
            box-shadow: 0px 2px 10px 0px rgba(0,0,0,0.7);
            border-radius: 12px;
        """)

        # Logo动画
        # self.movie = QMovie("ui/icon/AI助手圆脸_动效.gif")
        self.movie_label = QLabel()
        self.movie_label.setPixmap(QPixmap("ui/icon/DeepShell/icon_app_logo_DeepShell_圆角.png").scaled(124, 124))
        self.movie_label.setStyleSheet("""
            background: #E6E3E4;
            border-radius: 24px;
        """)
        self.movie_label.setFixedSize(QSize(96, 96))
        self.movie_label.setAlignment(Qt.AlignCenter)
        # self.movie_label.setMovie(self.movie)
        # self.movie.start()

        # 介绍文字
        self.welcome_label = QLabel(f"欢迎使用{ConfigManager().app_config['name']}")
        self.welcome_label.setStyleSheet("""
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 20px;
            color: #FFFEFE;
            background: transparent;
        """)
        self.welcome_label.setWordWrap(True)
        self.welcome_label.setFixedSize(QSize(200, 19))
        self.welcome_label.setAlignment(Qt.AlignCenter)
        self.intro_label = QLabel("DeepShell作为基于大语言模型的操作系统智能体，将为您提供个性化的操作系统体验,分析复杂需求，完成推理、决策，帮助您完成各种任务。")
        self.intro_label.setStyleSheet("""
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #B3B3B3;
            background: transparent;
        """)
        self.intro_label.setWordWrap(True)
        self.intro_label.setFixedSize(QSize(380, 64))
        self.intro_label.setAlignment(Qt.AlignLeft)

        # 导航页布局
        layout = QVBoxLayout()
        layout.addItem(QSpacerItem(10, 132, QSizePolicy.Expanding, QSizePolicy.Fixed))
        layout.addWidget(self.movie_label, alignment=Qt.AlignCenter)
        layout.addItem(QSpacerItem(10, 30, QSizePolicy.Expanding, QSizePolicy.Fixed))
        layout.addWidget(self.welcome_label, alignment=Qt.AlignCenter)
        layout.addItem(QSpacerItem(10, 17, QSizePolicy.Expanding, QSizePolicy.Fixed))
        layout.addWidget(self.intro_label, alignment=Qt.AlignCenter)
        layout.addStretch()
        self.setLayout(layout)


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    window = ChatIntroPage()
    window.show()
    sys.exit(app.exec_())