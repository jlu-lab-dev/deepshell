# api_config_page.py

import sys
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QApplication, QDesktopWidget, QComboBox, QAction
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QRectF
from PyQt5.QtGui import QIcon, QPainter, QColor, QPainterPath

from config.config_manager import ConfigManager

isClear = False


class ApiKeyConfigPage(QWidget):
    """
    一个自包含的API Key配置窗口。
    这个类合并了原先的 ApiKeyConfigPage (容器) 和 ApiKeyConfigMainWindow (内容) 的功能，
    以简化结构并消除冗余。
    """
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super(ApiKeyConfigPage, self).__init__(parent)

        # 1. 窗口基础设置 (原 ApiKeyConfigPage 的职责)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(450, 480)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setObjectName('api_config_page')
        self.setStyleSheet(
            '''
            #api_config_page{
                /* 这个背景色实际上由 paintEvent 绘制, 但保留样式表可用于其他属性 */
                background-color: transparent;
                border-radius: 15px;
                border: 1px solid #1e3a5f;
            }
            '''
        )

        # 初始化ConfigManager和service_keys (原 ApiKeyConfigMainWindow 的职责)
        self.service_keys = {
            "online-api-key": "API Key", "offline-api-key": "API Key",
            "model-address": "模型地址（非必需，应填入IP地址，默认 ollama 仓库）"
        }
        self.configManager = ConfigManager()

        # 2. 创建并组织所有UI组件
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 创建顶部栏
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)

        # 创建内容区域 (原 ApiKeyConfigMainWindow 的职责)
        content_layout = self.create_content_area()
        main_layout.addLayout(content_layout)

        # 创建底部按钮区域
        bottom_button_layout = self.create_buttons_layout()
        main_layout.addLayout(bottom_button_layout)

    # --- UI 创建辅助方法 ---

    def create_top_bar(self):
        setting_page_title = BoxTitle(self)
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(15, 0, 15, 0)
        title_label = QLabel("配置")
        title_label.setStyleSheet("font-size: 16px; color: #FFFFFF; font-weight: bold;")
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            '''
            QPushButton{background-color:transparent;border:none;}
            QPushButton:hover {background-color: rgba(42, 67, 101, 150); border-radius: 12px;}
            '''
        )
        close_btn.setIcon(QIcon('ui/icon/icon_关闭_窗口模式@2x.png'))
        close_btn.setIconSize(QSize(20, 20))
        close_btn.clicked.connect(self.close)
        top_bar_layout.addWidget(title_label)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(close_btn)
        setting_page_title.setLayout(top_bar_layout)
        return setting_page_title

    def create_content_area(self):
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 15, 0, 0)
        content_layout.setSpacing(20)

        self.online_service_box, self.online_inputs = self.create_service_box("在线模型",
                                                                              [("online-api-key", "API Key")])
        content_layout.addWidget(self.online_service_box)

        self.offline_service_box, self.offline_inputs = self.create_service_box(
            "离线模型",
            [("model-address", "模型地址（非必需，应填入IP地址，默认 ollama 仓库）"), ("offline-api-key", "Token（非必需）")]
        )
        content_layout.addWidget(self.offline_service_box)
        return content_layout

    def create_service_box(self, service_name, fields):
        service_box = QWidget()
        service_box_layout = QVBoxLayout(service_box)
        service_box_layout.setSpacing(12)
        service_label = QLabel(service_name)
        service_label.setStyleSheet("font-weight: bold; font-size:16px; color: #ccd6f6;")
        service_box_layout.addWidget(service_label)
        field_inputs = {}
        drop_down_box = QComboBox()
        if service_name == "在线模型":
            drop_down_box.addItems(["阿里云百炼", "DeepSeek"])
            field_inputs["model"] = drop_down_box
        elif service_name == "离线模型":
            drop_down_box.addItems(["DeepSeek-R1:1.5B", "openai兼容协议"])
            field_inputs["protocol"] = drop_down_box
        drop_down_box.setStyleSheet("""
            QComboBox { border: 1px solid #2a4365; border-radius: 5px; padding: 6px 12px; font-size: 14px; color: #ccd6f6; background-color: #122a4c; min-height: 28px; }
            QComboBox:hover { border-color: #64ffda; }
            QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: right center; width: 24px; border-left: 1px solid #2a4365; }
            QComboBox::down-arrow { image: url(ui/icon/icon_下拉框_箭头.png); width: 12px; height: 12px; }
            QComboBox QAbstractItemView { border: 1px solid #2a4365; border-radius: 5px; outline: none; color: #ccd6f6; background-color: #0a192f; padding: 4px 0; margin: 2px 0; }
            QComboBox QAbstractItemView::item { height: 18px; padding: 12px 24px; font-size: 15px; border-bottom: 1px solid #122a4c; }
            QComboBox QAbstractItemView::item:hover { background-color: #122a4c; }
            QComboBox QAbstractItemView::item:selected { background-color: #1e3a5f; }
        """)
        service_box_layout.addWidget(drop_down_box)
        for field_name, placeholder in fields:
            field_input = QLineEdit()
            model = drop_down_box.currentText()
            existing_value = self.configManager.get_online_api_key(model) if field_name == "online-api-key" else None
            if existing_value:
                field_input.setText(existing_value)
            else:
                field_input.setPlaceholderText(placeholder)
            if placeholder == "API Key":
                field_input.setEchoMode(QLineEdit.Password)
                toggle_action = QAction(QIcon('ui/icon/icon_眼睛_睁开.png'), "Show/Hide", field_input)
                toggle_action.triggered.connect(
                    lambda checked, fi=field_input, ta=toggle_action: self.toggle_echo_mode(fi, ta))
                field_input.addAction(toggle_action, QLineEdit.TrailingPosition)
            field_input.setStyleSheet("""
                QLineEdit { padding-left: 8px; padding-right: 30px; border: 1px solid #2a4365; border-radius: 5px; padding: 8px 12px; font-size: 14px; background-color: #122a4c; color: #ccd6f6; }
                QLineEdit:hover { border-color: #64ffda; }
            """)
            field_inputs[field_name] = field_input
            service_box_layout.addWidget(field_input)
        service_box_layout.setContentsMargins(20, 0, 20, 0)
        service_box.setStyleSheet("QWidget { border: none; background-color: transparent; }")
        if service_name == "在线模型":
            def update_api_key():
                model = drop_down_box.currentText()
                new_api_key = self.configManager.get_online_api_key(model)
                if "online-api-key" in field_inputs:
                    field_inputs["online-api-key"].setText(new_api_key or "")
                    field_inputs["online-api-key"].setPlaceholderText("Token（必需）")

            drop_down_box.currentIndexChanged.connect(update_api_key)
        return service_box, field_inputs

    def create_buttons_layout(self):
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)
        bottom_layout.setContentsMargins(20, 10, 20, 20)

        self.clear_button = QPushButton("清空")
        self.clear_button.setStyleSheet("""
            QPushButton { background-color: #2a4365; color: #ccd6f6; font-weight: bold; padding: 10px 20px; border-radius: 5px; border: 1px solid #2a4365; }
            QPushButton:hover { background-color: #35537e; }
        """)
        self.clear_button.setFixedWidth(80)
        self.clear_button.clicked.connect(self.clear_inputs)

        self.confirm_button = QPushButton("一键部署")
        self.confirm_button.setStyleSheet("""
            QPushButton { background-color: #00aaff; color: white; font-weight: bold; padding: 10px 20px; border-radius: 5px; border: none; }
            QPushButton:hover { background-color: #0099e6; }
        """)
        self.confirm_button.setFixedWidth(100)
        self.confirm_button.clicked.connect(self.confirm_and_close)  # 连接到新的组合槽函数

        bottom_layout.addStretch(1)
        bottom_layout.addWidget(self.clear_button)
        bottom_layout.addWidget(self.confirm_button)
        return bottom_layout

    # --- 槽函数 (Slots) 和 事件处理 (Event Handlers) ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 15, 15)
        painter.fillPath(path, QColor("#0a1f2f"))  # 注意这里颜色代码有误，应为 #0a192f

    def move_to_center(self):
        desktop = QDesktopWidget()
        target_screen_geometry = desktop.screenGeometry()
        self.move(int(target_screen_geometry.center().x() - self.width() / 2),
                  int(target_screen_geometry.center().y() - self.height() / 2))

    def toggle_echo_mode(self, line_edit, action):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            action.setIcon(QIcon('ui/icon/icon_眼睛_闭合.png'))
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            action.setIcon(QIcon('ui/icon/icon_眼睛_睁开.png'))

    def confirm_and_close(self):
        """保存配置并关闭窗口。"""
        # 保存逻辑
        online_api_key = self.online_inputs["online-api-key"].text()
        model = self.online_inputs["model"].currentText()
        global isClear
        if not isClear and not online_api_key:
            self.close()  # 如果没输入任何东西，直接关闭
            return
        if isClear and not online_api_key:
            self.configManager.set_online_api_key("", model)
        if online_api_key:
            self.configManager.set_online_api_key(online_api_key, model)

        # 关闭窗口
        self.close()

    def clear_inputs(self):
        global isClear
        isClear = True
        # 使用更准确的 findChildren 来只查找本窗口内的 QLineEdit
        for widget in self.findChildren(QLineEdit):
            widget.clear()
        for field_name, widget in self.online_inputs.items():
            if isinstance(widget, QLineEdit): widget.setPlaceholderText(self.service_keys.get(field_name, ""))
        for field_name, widget in self.offline_inputs.items():
            if isinstance(widget, QLineEdit): widget.setPlaceholderText(self.service_keys.get(field_name, ""))


class BoxTitle(QWidget):
    # 这个类保持不变，因为它职责清晰且独立
    def __init__(self, *args, **kwargs):
        super(BoxTitle, self).__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName('box_title')
        self.setStyleSheet('''
            #box_title{
                background-color: transparent;
                border-bottom: 1px solid #1e3a5f;
            }
        ''')
        self.setFixedHeight(50)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = True
            self.offset = event.globalPos() - self.window().pos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'moving') and self.moving and event.buttons() & Qt.LeftButton:
            self.window().move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = False