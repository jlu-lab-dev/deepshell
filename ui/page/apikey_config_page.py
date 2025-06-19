from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QApplication, QDesktopWidget, QComboBox, QAction
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QIcon, QPainter, QColor, QLinearGradient, QPen

from config.config_manager import ConfigManager
from utils.auto_ollama import OllamaTask

#isClear用于判断点击确认后，是否要清空输入框
isClear = False

class ApiKeyConfigPage(QWidget):
    # 定义关闭信号
    closed = pyqtSignal()
    # showSettingsPage = pyqtSignal()
    def __init__(self, parent=None):
        super(ApiKeyConfigPage, self).__init__(parent)
        layout = QVBoxLayout(self)  # 包含顶栏和主要内容
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)   # Qt.Dialog主要用于在任务栏隐藏图标
        self.resize(450, 500)
        
        # 背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
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
        deploy_button.clicked.connect(self.deploy_model) # Connect the button click
        deploy_button_layout.addStretch(1)
        deploy_button_layout.addWidget(deploy_button)
        deploy_button_layout.addStretch(1)

        # Status label for deployment
        self.deploy_status_label = QLabel("")
        self.deploy_status_label.setAlignment(Qt.AlignCenter)
        self.deploy_status_label.setStyleSheet("color: #555; font-size: 12px;")

        deploy_layout.addLayout(deploy_button_layout)
        deploy_layout.addWidget(self.deploy_status_label)
        deploy_layout.setContentsMargins(20, 10, 20, 10)

        layout.addLayout(deploy_layout)

        layout.setContentsMargins(0, 0, 0, 0)

        # Initialize OllamaTask
        self.ollama_task = OllamaTask()
        self.ollama_task.update_signal.connect(self.update_deploy_status)
        
           
    def create_top_bar(self):
        setting_page_title = BoxTitle(self)

        #创建顶部栏
        top_bar_layout = QHBoxLayout()

        title_label = QLabel("配置")
        title_label.setStyleSheet("font-size: 16px; color: black;")

        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            '''
            QPushButton{background-color:transparent;border:none;color:white;}
            '''
        )

        close_btn.setIcon(QIcon('ui/icon/icon_关闭_窗口模式@2x.png'))
        close_btn.setIconSize(QSize(24, 24))
        close_btn.clicked.connect(self.close)
        close_btn.setFixedSize(24, 24)

        top_bar_layout.addWidget(title_label)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(close_btn)

        setting_page_title.setLayout(top_bar_layout) 
        
        return setting_page_title

    """
        替换为SettingPage的move_to_center函数，使其显示在屏幕中央
    """

    def move_to_center(self):
        # 移动到窗口中心位置
        # 获取屏幕总数和屏幕几何数据
        desktop = QDesktopWidget()
        screen_count = desktop.screenCount()
        if screen_count > 1:
            # 多屏情况下，用第一个屏幕
            target_screen_index = 0
            # 获取目标屏幕的几何信息
            target_screen_geometry = desktop.screenGeometry(target_screen_index)
        else:
            # 单屏情况下使用默认屏幕
            target_screen_geometry = desktop.screenGeometry()

        # 计算窗口移动位置到屏幕右下角
        right = target_screen_geometry.right()
        bottom = target_screen_geometry.bottom()
        self.move(int(right / 2 - self.width() / 2), int(bottom / 2 - self.height() / 2))
        
    #鼠标移动，拖拽窗口实现
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if(self.moving):
            self.move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        if(event.button() == Qt.LeftButton):
            self.moving = False

    def paintEvent(self, event):
        #画圆角
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 设置抗锯齿，让圆角更加平滑
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        painter.setPen(QColor(0, 0, 0, 10))  # 黑色，透明度设置为10
        painter.setBrush(self.palette().window().color())#设置画刷为窗口背景颜色
        radius = 15 #设置圆角半径

        bounds = self.rect()  # 获取窗口的边界
        # 绘制阴影
        shadow = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
        shadow.setColorAt(0, QColor(100, 100, 100, 50))

        # 设置阴影的模糊半径
        painter.setPen(QPen(shadow, 1))
        painter.drawRoundedRect(self.rect(), radius, radius)

    def openSettingPage(self):
        # self.showSettingsPage.emit()
        # print("信号已经发送")
        self.close()
        # self.parent().setting_main_window.update_status()
        # self.parent().show()

    def deploy_model(self):
        """Starts the Ollama deployment task."""
        self.deploy_status_label.setText("开始部署...")
        # Disable button during deployment? (Optional)
        # self.findChild(QPushButton, "一键部署模型").setEnabled(False)
        self.ollama_task.start()

    def update_deploy_status(self, message):
        """Updates the deployment status label."""
        self.deploy_status_label.setText(message)
        # Re-enable button if finished or failed (Optional)
        # if "已部署" in message or "失败" in message:
        #     self.findChild(QPushButton, "一键部署模型").setEnabled(True)


class ApiKeyConfigMainWindow(QWidget):
    def __init__(self, parent=None):
        super(ApiKeyConfigMainWindow, self).__init__(parent)
        self.resize(490, 500)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint) #Qt.Dialog主要用于在任务栏隐藏图标

        # 背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 实现圆角
        self.setObjectName('mainwindow')
        self.radius = 15

        # 内容框
        main_layout = QVBoxLayout(self)

        # 定义服务配置项的字典,存储placeholder，后续点击清空的时候需要用到
        self.service_keys = {
            "online-api-key": "API Key",
            "offline-api-key":"API Key",
            "model-address": "模型地址",
            "model-name": "模型名称"
        }

        self.configManager = ConfigManager()

        self.online_service_box,self.online_inputs = self.create_service_box("在线模型",[("online-api-key", "API Key")])


        main_layout.addWidget(self.online_service_box)

        self.offline_service_box, self.offline_inputs = self.create_service_box(
            "离线模型",
            [("model-address", "模型地址"), ("model-name", "模型名称"),
             ("offline-api-key", "API Key")])


        #加入主布局中
        main_layout.addWidget(self.offline_service_box)

        # 确定和清空框
        button_layout = self.create_buttons()
        main_layout.addLayout(button_layout)

    def create_ai_model_section(self):
        # ai大模型
        ai_model_layout = QVBoxLayout()
        ai_model_layout.setSpacing(15)
        ai_model_layout.setContentsMargins(10, 10, 10, 10)

        ai_model_label = QLabel("AI大模型")
        ai_model_label.setStyleSheet("font-weight: bold;")
        ai_model_layout.addWidget(ai_model_label)


        return ai_model_layout

    def create_service_box(self, service_name, fields):
        # 服务配置项
        service_box = QWidget()
        service_box_layout = QVBoxLayout(service_box)
        service_box_layout.setSpacing(10)

        service_label = QLabel(service_name)
        service_label.setStyleSheet("font-weight: bold; font-size:16px;")
        service_box_layout.addWidget(service_label)

        # 创建一个字典来保存字段名称与对应的 QLineEdit 控件
        field_inputs = {}

        drop_down_box = QComboBox()
        if service_name == "在线模型":
            drop_down_box.addItem("阿里云百炼")
            drop_down_box.addItem("DeepSeek")
            field_inputs["model"] = drop_down_box
        elif service_name == "离线模型":
            drop_down_box.addItem("ollama")
            drop_down_box.addItem("openai兼容协议")
            field_inputs["protocol"] = drop_down_box

        drop_down_box.setStyleSheet("""
                        QComboBox {
                            border: 1px solid #dcdcdc;
                            border-radius: 5px;
                            padding: 6px 12px;
                            font-size: 14px;
                            background-color: white;
                            min-height: 28px;
                        }
                        QComboBox:hover {
                            border-color: #00aaff;
                        }
                        QComboBox::drop-down {
                            subcontrol-origin: padding;
                            subcontrol-position: right center;
                            width: 24px;
                            border-left: 1px solid #dcdcdc;
                        }
                        QComboBox::down-arrow {
                            image: url(ui/icon/icon_下拉框_箭头.png);
                            width: 12px;
                            height: 12px;
                        }
                        QComboBox QAbstractItemView {
                            border: 1px solid #dcdcdc;
                            border-radius: 5px;
                            outline: none;
                            background: white;
                            padding: 4px 0;
                            margin: 2px 0;
                            min-width: 120px;
                        }
                        QComboBox QAbstractItemView::item {
                            height: 18px;
                            padding: 12px 24px;
                            font-size: 15px;
                            border-bottom: 1px solid #f5f5f5;
                            color: #333;
                        }
                        QComboBox QAbstractItemView::item:hover {
                            background-color: #f0faff;
                        }
                        QComboBox QAbstractItemView::item:selected {
                            background-color: #00aaff;
                            color: white;
                        }
                    """)

        service_box_layout.addWidget(drop_down_box)

        model = drop_down_box.currentText()

        for field_name, placeholder in fields:
            field_label = QLabel(field_name)
            field_input = QLineEdit()

            # 检查配置文件中是否存在该键
            existing_value = None
            if field_name == "online-api-key":
                existing_value = self.configManager.get_online_api_key(model)

            # 根据是否存在键来设置 placeholder
            if existing_value:
                field_input.setText(existing_value)
            else:
                field_input.setPlaceholderText(placeholder)

            if placeholder == "API Key":
                # 设置为密码模式
                field_input.setEchoMode(QLineEdit.Password)

                # 创建眼睛图标动作
                toggle_action = QAction(field_input)
                toggle_action.setIcon(QIcon('ui/icon/icon_眼睛_睁开.png'))
                toggle_action.triggered.connect(lambda: self.toggle_echo_mode(field_input, toggle_action))

                # 添加动作到文本框右侧
                field_input.addAction(toggle_action, QLineEdit.TrailingPosition)
                field_input.setStyleSheet("""
                               QLineEdit {
                                   padding-right: 30px;
                                   border: 1px solid #dcdcdc;
                                   border-radius: 5px;
                                   padding: 8px 12px;
                                   font-size: 14px;
                               }
                               QLineEdit:hover {
                                   border-color: #00aaff;
                               }
                           """)

            # 保存输入框的引用
            field_inputs[field_name] = field_input
            service_box_layout.setContentsMargins(20,0,20,0)

            service_box_layout.addWidget(field_input)

        service_box.setStyleSheet(
            "QWidget { border: none; border-radius: 8px; padding: 10px; }"
        )

        if service_name == "在线模型":
            def update_api_key():
                # 重新获取当前选中的模型
                model = drop_down_box.currentText()
                # 从配置文件中获取对应模型的 API Key
                new_api_key = self.configManager.get_online_api_key(model)
                # 更新 API Key 文本框的内容
                if "online-api-key" in field_inputs:
                    field_inputs["online-api-key"].setText(new_api_key if new_api_key else "API Key")

            # 连接信号，当用户更改选项时调用更新函数
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
        # 确定和清空按钮
        button_layout = QHBoxLayout()

        clear_button = QPushButton("清空")
        clear_button.setStyleSheet(
            "background-color: #f0f0f0; color: #4d4f53; font-weight: bold; padding: 10px 20px; border-radius: 5px;border:0.5px solid #7d7d7d"
        )
        clear_button.setFixedWidth(80)
        clear_button.clicked.connect(self.clear_inputs)

        self.confirm_button = QPushButton("确认")
        self.confirm_button.setStyleSheet(
            "background-color: #00aaff; color: white; font-weight: bold; padding: 10px 20px; border-radius: 5px;"
        )
        self.confirm_button.setFixedWidth(80)
        self.confirm_button.clicked.connect(self.confirm)


        button_layout.addStretch(1)
        button_layout.addWidget(clear_button)
        button_layout.addWidget(self.confirm_button)
        # Adjusted top margin to make space for the deploy button area in the parent
        button_layout.setContentsMargins(0, 5, 20, 10) # Reduced top margin further

        return button_layout


    def confirm(self):
        # 从字段字典中获取 QLineEdit 控件的值
        """
        online
        """
        online_api_key = self.online_inputs["online-api-key"].text()

        model = self.online_inputs["model"].currentText()

        global isClear
        # 1、没有点击清空，且输入框为空，则不执行任何操作
        if not isClear and not online_api_key:
            return

        # 2、点击清空，且输入框为空，则清空配置文件
        if isClear and not online_api_key:
            self.configManager.set_online_api_key("",model)
            return

        # 检查并设置配置，记录成功或失败的状态
        success = True

        # 3、点击确认，输入框有值，则设置配置

        if online_api_key:
            if not self.configManager.set_online_api_key(online_api_key,model):
                success = False


    def clear_inputs(self):
        # 清空按钮
        global isClear
        isClear = True

        for widget in self.findChildren(QLineEdit):
            widget.clear()

        # 将 placeholder 文本恢复为原始值
        for field_name in self.online_inputs:
            if not field_name:
                self.online_inputs[field_name].setPlaceholderText(self.service_keys[field_name])

        for field_name in self.offline_inputs:
            if not field_name:
                self.offline_inputs[field_name].setPlaceholderText(self.service_keys[field_name])

class BoxTitle(QWidget):
    def __init__(self, *args, **kwargs):
        super(BoxTitle, self).__init__()
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName('box_title')
        self.setStyleSheet(
                '''
                #box_title{
                    border-left: 2px solid transparent;
                    border-top-left-radius: 15px;
                    border-top-right-radius: 15px;
                    background-color: white;
                    background-clip: padding-box; 
                }
                '''
            )
        self.installEventFilter(self)
        self.setFixedHeight(36)


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    api_key_config_page = ApiKeyConfigPage()
    api_key_config_page.show()
    sys.exit(app.exec_())
