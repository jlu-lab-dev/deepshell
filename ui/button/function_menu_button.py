from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize, QPoint,pyqtSignal

from ui.function_menu import FunctionMenu


class FunctionMenuButton(QPushButton):
    function_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QPushButton {
                width: 36px;
                height: 36px;
                background: #30425C;
                border-radius: 8px;
                opacity: 0.4;
            }
            QPushButton:hover {
                background-color: rgb(40, 60, 90);
                border-color: rgb(80, 100, 140);
            }
            QPushButton:pressed {
                background-color: rgb(24, 36, 54);
                border-color: rgb(48, 64, 96);
            }
        """)
        self.setIcon(QIcon("ui/icon/icon_输入框_切换.png"))
        self.setIconSize(QSize(16, 16))

        self.function_menu = FunctionMenu()
        self.function_menu.function_selected.connect(self.emit_function_signal)
        self.clicked.connect(self.show_function_menu)

    def show_function_menu(self):
        if self.function_menu.isHidden():
            # 动态计算位置
            btn_pos = self.mapToGlobal(QPoint(0, 0))
            # relative_pos = self.mapFromGlobal(btn_pos)
            x = btn_pos.x() - self.function_menu.width() + self.width() - 10
            y = btn_pos.y() - 6 - self.function_menu.height()
            print("x = {} y = {}".format(x, y))
            self.function_menu.move(x, y)
            self.function_menu.show()
            print("show function menu")
        else:
            self.function_menu.hide()

    def emit_function_signal(self, function_name):
        self.function_selected.emit(function_name)

