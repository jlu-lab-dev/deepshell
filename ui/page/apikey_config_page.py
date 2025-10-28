import sys
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QApplication, QDesktopWidget, QComboBox, QAction
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon

from config.config_manager import ConfigManager
from utils.auto_ollama import OllamaTask

# isClear用于判断点击确认后，是否要清空输入框
isClear = False


class ApiKeyConfigPage(QWidget):
    # 定义关闭信号
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super(ApiKeyConfigPage, self).__init__(parent)
        layout = QVBoxLayout(self)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.resize(450, 500)

        # --- Style Update Start ---
        # 移除背景透明设置
        # self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.setObjectName('api_config_page')
        # 应用深蓝色背景样式
        self.setStyleSheet(
            '''
            #api_config_page{
                background-color: #0a192f; /* 深蓝色背景 */
                border-radius: 15px;
                border: 1px solid #1e3a5f; /* 边框颜色调整 */
            }
            '''
        )
        # --- Style Update End ---

        # 顶部栏
        top_bar = self.create_top_bar()
        layout.addWidget(top_bar)

        # 主要内容
        self.setting_main_window = ApiKeyConfigMainWindow()
        self.setting_main_window.confirm_button.clicked.connect(self.openSettingPage)
        layout.addWidget(self.setting_main_window)

        # 一键部署区域
        deploy_layout = QVBoxLayout()
        deploy_layout.setSpacing(5)

        deploy_button_layout = QHBoxLayout()
        deploy_button = QPushButton("一键部署模型")
        deploy_button.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 10px 20px; border-radius: 5px;"
        )
        deploy_button.clicked.connect(self.deploy_model)
        deploy_button_layout.addStretch(1)
        deploy_button_layout.addWidget(deploy_button)
        deploy_button_layout.addStretch(1)

        # Status label for deployment
        self.deploy_status_label = QLabel("")
        self.deploy_status_label.setAlignment(Qt.AlignCenter)
        self.deploy_status_label.setStyleSheet("color: #a8b2d1; font-size: 12px;")  # 调整为亮色

        deploy_layout.addLayout(deploy_button_layout)
        deploy_layout.addWidget(self.deploy_status_label)
        deploy_layout.setContentsMargins(20, 10, 20, 10)

        layout.addLayout(deploy_layout)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Initialize OllamaTask
        self.ollama_task = OllamaTask()
        self.ollama_task.update_signal.connect(self.update_deploy_status)

    def create_top_bar(self):
        setting_page_title = BoxTitle(self)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(15, 0, 15, 0)

        title_label = QLabel("配置")
        # --- Style Update Start ---
        # 标题颜色改为白色以适应深色背景
        title_label.setStyleSheet("font-size: 16px; color: #FFFFFF; font-weight: bold;")
        # --- Style Update End ---

        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            '''
            QPushButton{
                background-color:transparent;
                border:none;
            }
            QPushButton:hover {
                background-color: rgba(42, 67, 101, 150); /* 悬停颜色调整 */
                border-radius: 12px;
            }
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

    def move_to_center(self):
        desktop = QDesktopWidget()
        target_screen_geometry = desktop.screenGeometry()
        self.move(int(target_screen_geometry.center().x() - self.width() / 2),
                  int(target_screen_geometry.center().y() - self.height() / 2))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if hasattr(self, 'moving') and self.moving and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = False

    def openSettingPage(self):
        self.close()

    def deploy_model(self):
        self.deploy_status_label.setText("开始部署...")
        self.ollama_task.start()

    def update_deploy_status(self, message):
        self.deploy_status_label.setText(message)


class ApiKeyConfigMainWindow(QWidget):
    def __init__(self, parent=None):
        super(ApiKeyConfigMainWindow, self).__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 保持主内容区透明以显示父窗口背景

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 10, 0, 0)

        self.service_keys = {
            "online-api-key": "API Key", "offline-api-key": "API Key",
            "model-address": "模型地址", "model-name": "模型名称"
        }
        self.configManager = ConfigManager()

        self.online_service_box, self.online_inputs = self.create_service_box("在线模型",
                                                                              [("online-api-key", "API Key")])
        main_layout.addWidget(self.online_service_box)

        self.offline_service_box, self.offline_inputs = self.create_service_box(
            "离线模型", [("model-address", "模型地址"), ("model-name", "模型名称"), ("offline-api-key", "API Key")]
        )
        main_layout.addWidget(self.offline_service_box)

        button_layout = self.create_buttons()
        main_layout.addLayout(button_layout)

    def create_service_box(self, service_name, fields):
        service_box = QWidget()
        service_box_layout = QVBoxLayout(service_box)
        service_box_layout.setSpacing(10)

        service_label = QLabel(service_name)
        # --- Style Update Start ---
        # 标签文字改为浅色
        service_label.setStyleSheet("font-weight: bold; font-size:16px; color: #ccd6f6;")
        # --- Style Update End ---
        service_box_layout.addWidget(service_label)

        field_inputs = {}
        drop_down_box = QComboBox()
        if service_name == "在线模型":
            drop_down_box.addItems(["阿里云百炼", "DeepSeek"])
            field_inputs["model"] = drop_down_box
        elif service_name == "离线模型":
            drop_down_box.addItems(["DeepSeek-R1:1.5B", "openai兼容协议"])
            field_inputs["protocol"] = drop_down_box

        # --- Style Update Start ---
        # ComboBox样式适配深色主题
        drop_down_box.setStyleSheet("""
            QComboBox {
                border: 1px solid #2a4365;
                border-radius: 5px; padding: 6px 12px;
                font-size: 14px; color: #ccd6f6;
                background-color: #122a4c;
                min-height: 28px;
            }
            QComboBox:hover { border-color: #64ffda; }
            QComboBox::drop-down {
                subcontrol-origin: padding; subcontrol-position: right center;
                width: 24px; border-left: 1px solid #2a4365;
            }
            QComboBox::down-arrow { image: url(ui/icon/icon_下拉框_箭头.png); width: 12px; height: 12px; }
            QComboBox QAbstractItemView {
                border: 1px solid #2a4365; border-radius: 5px;
                outline: none; color: #ccd6f6;
                background-color: #0a192f;
                padding: 4px 0; margin: 2px 0;
            }
            QComboBox QAbstractItemView::item {
                height: 18px; padding: 12px 24px; font-size: 15px;
                border-bottom: 1px solid #122a4c;
            }
            QComboBox QAbstractItemView::item:hover { background-color: #122a4c; }
            QComboBox QAbstractItemView::item:selected { background-color: #1e3a5f; }
        """)
        # --- Style Update End ---
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

            # --- Style Update Start ---
            # QLineEdit样式适配深色主题, 并增加左边距解决密码显示问题
            field_input.setStyleSheet("""
                QLineEdit {
                    padding-left: 8px; /* 解决密码字符被截断的问题 */
                    padding-right: 30px;
                    border: 1px solid #2a4365;
                    border-radius: 5px;
                    padding: 8px 12px;
                    font-size: 14px;
                    background-color: #122a4c; /* 深色背景 */
                    color: #ccd6f6; /* 亮色文字 */
                }
                QLineEdit:hover {
                    border-color: #64ffda; /* 悬停高亮颜色 */
                }
            """)
            # --- Style Update End ---
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
                    field_inputs["online-api-key"].setPlaceholderText("API Key")

            drop_down_box.currentIndexChanged.connect(update_api_key)

        return service_box, field_inputs

    def toggle_echo_mode(self, line_edit, action):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            action.setIcon(QIcon('ui/icon/icon_眼睛_闭合.png'))
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            action.setIcon(QIcon('ui/icon/icon_眼睛_睁开.png'))

    def create_buttons(self):
        button_layout = QHBoxLayout()
        clear_button = QPushButton("清空")
        # --- Style Update Start ---
        # "清空"按钮适配深色主题
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #2a4365; color: #ccd6f6;
                font-weight: bold; padding: 10px 20px;
                border-radius: 5px; border: 1px solid #2a4365;
            }
            QPushButton:hover { background-color: #35537e; }
        """)
        # --- Style Update End ---
        clear_button.setFixedWidth(80)
        clear_button.clicked.connect(self.clear_inputs)

        self.confirm_button = QPushButton("确认")
        # --- Style Update Start ---
        # "确认"按钮样式微调
        self.confirm_button.setStyleSheet("""
            QPushButton {
                background-color: #00aaff; color: white;
                font-weight: bold; padding: 10px 20px;
                border-radius: 5px; border: none;
            }
            QPushButton:hover { background-color: #0099e6; }
        """)
        # --- Style Update End ---
        self.confirm_button.setFixedWidth(80)
        self.confirm_button.clicked.connect(self.confirm)

        button_layout.addStretch(1)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(self.confirm_button)
        button_layout.setContentsMargins(0, 5, 20, 10)
        return button_layout

    def confirm(self):
        online_api_key = self.online_inputs["online-api-key"].text()
        model = self.online_inputs["model"].currentText()
        global isClear
        if not isClear and not online_api_key: return
        if isClear and not online_api_key:
            self.configManager.set_online_api_key("", model)
            return
        if online_api_key:
            self.configManager.set_online_api_key(online_api_key, model)

    def clear_inputs(self):
        global isClear
        isClear = True
        for widget in self.findChildren(QLineEdit):
            widget.clear()
        for field_name, widget in self.online_inputs.items():
            if isinstance(widget, QLineEdit): widget.setPlaceholderText(self.service_keys.get(field_name, ""))
        for field_name, widget in self.offline_inputs.items():
            if isinstance(widget, QLineEdit): widget.setPlaceholderText(self.service_keys.get(field_name, ""))


class BoxTitle(QWidget):
    def __init__(self, *args, **kwargs):
        super(BoxTitle, self).__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName('box_title')
        # --- Style Update Start ---
        # 标题栏适配深色主题
        self.setStyleSheet('''
            #box_title{
                background-color: transparent;
                border-bottom: 1px solid #1e3a5f; /* 分割线颜色调整 */
            }
        ''')
        # --- Style Update End ---
        self.setFixedHeight(50)
