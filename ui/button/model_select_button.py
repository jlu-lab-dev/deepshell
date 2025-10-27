from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QPushButton, QMenu, QWidgetAction, QHBoxLayout, QLabel, QWidget
from PyQt5.QtGui import QIcon


class ModelSelectButton(QPushButton):
    model_switch = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 格式：界面名称:实际模型调用的模型名称(model.yaml的key)
        self.model_name_dict = {
            "DeepSeek-V3": "DeepSeek-V3",
            "通义千问": "Qwen-Max",
            "讯飞星火": "XunFei-generalv3.5",
            "DeepSeek-R1(离线)": "DeepSeek-R1-1.5B"
        }
        # 格式：界面名称:界面logo
        self.model_icon_path = {
            "DeepSeek-V3": "ui/icon/icon_模型切换_deepseek.png",
            "通义千问": "ui/icon/icon_模型切换_阿里通义.png",
            "讯飞星火": "ui/icon/icon_模型切换_讯飞星火.png",
            "DeepSeek-R1(离线)": "ui/icon/icon_模型切换_deepseek.png",
        }
        self.current_model = "DeepSeek-V3"
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
			QPushButton{
                    width: 162px;
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

        # 模型图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.update_icon()

        # 模型名称
        self.name_label = QLabel(self.current_model)
        self.name_label.setStyleSheet("""
            width: 87px;
            height: 16px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            line-height: 18px;
        """)

        # 下拉箭头
        arrow_label = QLabel()
        arrow_label.setFixedSize(16, 16)
        arrow_label.setStyleSheet("""
                    background: rgba(51,51,51,0);
                """)
        arrow_label.setPixmap(QIcon("ui/icon/icon_输入框_下拉框.png").pixmap(16, 16))

        # 添加到布局
        layout = QHBoxLayout()
        layout.setSpacing(7)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.name_label)
        layout.addWidget(arrow_label, Qt.AlignRight)
        self.setLayout(layout)

        # 创建下拉菜单
        self.menu = QMenu(self)
        self.menu.setStyleSheet("""
            QMenu {
                width: 162px;
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

        self.clicked.connect(self.show_menu)

    def create_menu_action(self, model_name, icon_path):
        """创建带图标的菜单项"""
        icon_label = QLabel()
        icon_label.setPixmap(QIcon(icon_path).pixmap(16, 16))

        name_label = QLabel(model_name)
        name_label.setStyleSheet("""
            width: 87px;
            height: 16px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            line-height: 18px;
        """)

        layout = QHBoxLayout()
        layout.setSpacing(7)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(name_label,1,Qt.AlignLeft)

        action_widget = QWidget()
        action_widget.setLayout(layout)
        action = QWidgetAction(self.menu)
        action.setDefaultWidget(action_widget)
        action.triggered.connect(lambda: self.set_current_model(model_name))

        return action

    def update_icon(self):
        """更新当前模型图标"""
        self.icon_label.setPixmap(
            QIcon(self.model_icon_path[self.current_model]).pixmap(16, 16))

    def set_current_model(self, model_name):
        """设置当前模型"""
        if model_name in self.model_icon_path:
            self.current_model = model_name
            self.name_label.setText(model_name)
            self.update_icon()
            self.model_switch.emit(self.model_name_dict[model_name])  # 根据显示的模型名字切换实际的模型英文名

    def show_menu(self):
        """显示下拉菜单（不包含当前已选模型）"""
        # 先清空菜单
        self.menu.clear()

        # 添加除当前模型外的其他选项
        for model_name, icon_path in self.model_icon_path.items():
            if model_name != self.current_model:
                action = self.create_menu_action(model_name, icon_path)
                self.menu.addAction(action)

        # 显示菜单
        self.menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

