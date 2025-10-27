from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton, QLabel, QMenu, QWidget, QWidgetAction, QHBoxLayout
from translation.language_dic import dic

class LeftLangSelectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.language_list = ['自动检测']
        for _,value in dic.items():
            self.language_list.append(value)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QPushButton {
                width: 120px;
                height: 36px;
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        """)

        self.current_language = "自动检测"
        self.language_label = QLabel(self.current_language)
        self.language_label.setStyleSheet('''
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            width: 87px;
            height: 16px;
            line-height: 18px;
        ''')

        arrow_label = QLabel()
        arrow_label.setFixedSize(16, 16)
        arrow_label.setPixmap(QIcon("ui/icon/icon_输入框_下拉框.png").pixmap(16, 16))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        layout.addWidget(self.language_label)
        layout.addWidget(arrow_label, alignment=Qt.AlignRight)

        # 初始化菜单
        self.menu = QMenu(self)
        self.menu.setStyleSheet("""
            QMenu {
                width:162px; 
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            QMenu::item {
                min-height: 36px;
            }
            QMenu::item:selected {
                background-color: #3c3c3c;
            }
        """)
        self.menu.raise_()
        self.clicked.connect(self.show_menu)

    def create_menu_action(self, lang_name):
        action_widget = QWidget()
        # action_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(action_widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        name_label = QLabel(lang_name)
        name_label.setStyleSheet("""
            width: 87px;
            height: 16px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            line-height: 18px;
        """)

        layout.addWidget(name_label)

        action = QWidgetAction(self.menu)
        action.setDefaultWidget(action_widget)
        action.triggered.connect(lambda: self.set_current_language(lang_name))
        return action

    def set_current_language(self, language):
        if language in self.language_list:
            self.current_language = language
            self.language_label.setText(language)

    def show_menu(self):
        self.menu.clear()
        for lang in self.language_list:
            if lang != self.current_language:
                action = self.create_menu_action(lang)
                self.menu.addAction(action)
        self.menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

class RightLangSelectButton(QPushButton):
    def __init__(self):
        super().__init__()
        self.language_list = []
        for _,value in dic.items():
            self.language_list.append(value)
        self.language_list.pop()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QPushButton {
                width: 120px;
                height: 36px;
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        """)

        self.current_language = "英语"
        self.language_label = QLabel(self.current_language)
        self.language_label.setStyleSheet('''
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            width: 87px;
            height: 16px;
            line-height: 18px;
        ''')

        arrow_label = QLabel()
        arrow_label.setFixedSize(16, 16)
        arrow_label.setPixmap(QIcon("ui/icon/icon_输入框_下拉框.png").pixmap(16, 16))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        layout.addWidget(self.language_label)
        layout.addWidget(arrow_label, alignment=Qt.AlignRight)

        # 初始化菜单
        self.menu = QMenu(self)
        self.menu.setStyleSheet("""
            QMenu {
                width:162px; 
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            QMenu::item {
                min-height: 36px;
            }
            QMenu::item:selected {
                background-color: #3c3c3c;
            }
        """)
        self.menu.raise_()
        self.clicked.connect(self.show_menu)

    def create_menu_action(self, lang_name):
        action_widget = QWidget()
        # action_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(action_widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        name_label = QLabel(lang_name)
        name_label.setStyleSheet("""
            width: 87px;
            height: 16px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            line-height: 18px;
        """)

        layout.addWidget(name_label)

        action = QWidgetAction(self.menu)
        action.setDefaultWidget(action_widget)
        action.triggered.connect(lambda: self.set_current_language(lang_name))
        return action

    def set_current_language(self, language):
        if language in self.language_list:
            self.current_language = language
            self.language_label.setText(language)

    def show_menu(self):
        self.menu.clear()
        for lang in self.language_list:
            if lang != self.current_language:
                action = self.create_menu_action(lang)
                self.menu.addAction(action)
        self.menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

def language_select_layout():
    left_box = LeftLangSelectButton()
    right_box = RightLangSelectButton()

    trans_button = QPushButton()
    trans_button.setStyleSheet("""
                background:rgba(51,51,51,0);
            """)
    trans_icon_path = "ui/icon/icon_翻译_切换.png"
    trans_button.setIcon(QIcon(trans_icon_path))
    trans_button.setIconSize(QSize(16, 13))
    trans_button.setFixedSize(16, 16)

    def on_trans_clicked():
        tmp = left_box.current_language
        left_box.set_current_language(right_box.current_language)
        right_box.set_current_language(tmp)

    trans_button.clicked.connect(on_trans_clicked)

    layout = QHBoxLayout()
    layout.setSpacing(12)
    layout.addWidget(left_box)
    layout.addWidget(trans_button)
    layout.addWidget(right_box)

    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        widget.hide()
    return layout




# def show_language_select_layout(layout):
#     for i in range(layout.count()):
#         widget = layout.itemAt(i).widget()
#         widget.show()

# def test_layout():
#     app = QApplication([])
#     window = QWidget()
#
#     layout = language_select_layout()
#     show_language_select_layout(layout)
#     # 将布局设置到窗口上
#     window.setLayout(layout)
#     window.setWindowTitle("语言选择")
#     window.setMinimumSize(600, 400)  # 设置最小尺寸确保布局可见
#     window.show()
#     app.exec_()

# if __name__ == "__main__":
#     test_layout()

