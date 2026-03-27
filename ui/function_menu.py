from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QPainterPath
from PyQt5.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QPushButton, QLabel


class FunctionMenu(QWidget):
    function_selected = pyqtSignal(str)  # 定义信号

    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(348, 432)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        # self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                width: 432px;
                height: 432px;
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 12px;
            }
        """)
        # self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)

        # 主布局：网格布局（4列）
        grid = QGridLayout()
        grid.setContentsMargins(30, 30, 30,45)
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(30)

        # 定义按钮数据（文本，图标路径）
        buttons = [
            ("智能问答", "ui/icon/DeepShell/icon_DeepShell_智能助手.png"),
            ("AI Agent", "ui/icon/DeepShell/icon_DeepShell_系统功能.png"),
            ("语种翻译", "ui/icon/DeepShell/icon_DeepShell_语种翻译.png"),
            ("AI 识图", "ui/icon/DeepShell/icon_DeepShell_AI识图.png"),
            ("知识库", "ui/icon/DeepShell/icon_DeepShell_知识库.png"),
            ("AI PPT", "ui/icon/DeepShell/icon_DeepShell_AI_PPT.png"),
            ("AI 表格", "ui/icon/DeepShell/icon_DeepShell_AI表格.png"),
            ("会议记录", "ui/icon/DeepShell/icon_DeepShell_会议记录.png"),
            ("思维导图", "ui/icon/DeepShell/icon_DeepShell_思维导图.png"),
        ]

        # 创建并添加按钮
        positions = [(i // 3, i % 3) for i in range(9)]
        for (text, icon), pos in zip(buttons, positions):
            widget = self.create_button(text, icon, pos)
            grid.addWidget(widget, *pos)

        self.setLayout(grid)
        self.hide()

    def create_button(self, text, icon_path, pos):
        #按钮+文本
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(13)  # 按钮与文本间距

        container.setStyleSheet("""
                    QWidget {
                        background: transparent;
                        border: none;
                    }
                """)

        # 创建主按钮容器
        btn = QPushButton()
        btn.setFixedSize(72, 72)
        btn.setIcon(self.rounded_icon(icon_path, 72))
        btn.setIconSize(QSize(72, 72))

        # 添加带参数的点击事件
        btn.clicked.connect(lambda checked, t=text: self.emit_function_signal(t))

        text_label = QLabel(text)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("""
                    QLabel {
                        width: 56px;
                        height: 14px;
                        font-family: Microsoft YaHei;
                        font-weight: 400;
                        font-size: 14px;
                        color: #FFFFFF;
                    }
                """)

        # 按钮样式
        btn.setStyleSheet("""
            QPushButton {
                width: 72px;
                height: 72px;
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
                border-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
                border-color: #3c3c3c;
            }
        """)
        container_layout.addWidget(btn,0,Qt.AlignCenter)
        container_layout.addWidget(text_label,0,Qt.AlignCenter)
        return container

    def rounded_icon(self, path, size, radius=10):
        pixmap = QPixmap(path).scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        mask = QPixmap(size, size)
        mask.fill(Qt.transparent)
        painter = QPainter(mask)
        painter.setRenderHint(QPainter.Antialiasing)
        painter_path = QPainterPath()
        painter_path.addRoundedRect(0, 0, size, size, radius, radius)
        painter.setClipPath(painter_path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return QIcon(mask)

    def emit_function_signal(self, function_name):
        """统一信号发射方法"""
        self.function_selected.emit(function_name)
        self.hide()
