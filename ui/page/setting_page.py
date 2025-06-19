import webbrowser
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QDesktopWidget
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPainter, QColor, QLinearGradient, QPen
from ui.page.apikey_config_page import ApiKeyConfigPage
from config.config_manager import ConfigManager


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super(SettingsPage, self).__init__(parent)
        layout = QVBoxLayout(self)  # 包含顶栏和主要内容
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint) # Qt.Dialog主要用于在任务栏隐藏图标
        self.resize(450, 350)
        # 背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # # 当配置界面点击确定之后，使用槽信号，打开设置界面
        # self.apiKeyConfigPage = ApiKeyConfigPage()
        # self.apiKeyConfigPage.showSettingsPage.connect(self.onShowSettingsPage)

        # 顶部栏
        top_bar = self.create_top_bar()
        layout.addWidget(top_bar)
        
        # 主要内容
        self.setting_main_window = SettingsMainWindow()
        layout.addWidget(self.setting_main_window)
        
        # 添加按钮的点击事件
        self.setting_main_window.configure_button.clicked.connect(self.openApiKeyConfigPage)
        
        layout.setContentsMargins(0, 0, 0, 0)
        
    def openApiKeyConfigPage(self):
        # 创建并显示 APIKeyConfigPage 窗口
        self.apiKeyConfigPage = ApiKeyConfigPage(self)
        self.hide()
        self.apiKeyConfigPage.show()
        # 将窗口置顶
        self.apiKeyConfigPage.raise_()

    # def onShowSettingsPage(self):
    #     # 当配置界面点击确定之后，打开设置界面
    #     print("信号接受成功")
    #     self.show()
           
    def create_top_bar(self):
        setting_page_title = BoxTitle(self)

        #创建顶部栏
        top_bar_layout = QHBoxLayout()

        title_label = QLabel("设置")
        title_label.setStyleSheet("font-size: 16px; color: black;")

        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            '''
            QPushButton{background-color:transparent;border:none;color:white;}
            '''
        )

        close_btn.setIcon(QIcon('../../data/close.png'))
        close_btn.setIconSize(QSize(24, 24));
        close_btn.clicked.connect(self.close)
        close_btn.setFixedSize(24, 24)

        top_bar_layout.addWidget(title_label)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(close_btn)

        setting_page_title.setLayout(top_bar_layout) 
        
        return setting_page_title


    def move_to_center(self):
        #移动到窗口中心位置
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
        self.move(int(right/2 - self.width()/2), int(bottom/2 - self.height()/2))

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



class SettingsMainWindow(QWidget):
    def __init__(self, parent=None):
        super(SettingsMainWindow, self).__init__(parent)
        self.moving = False
        main_layout = QVBoxLayout(self)

        self.status_list = []

        #实现圆角
        self.setObjectName('mainwindow')
        self.radius = 10

        # 背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)


        # 初始化服务状态字典
        self.services_status = {
            "百炼-问答绘图服务": "待添加",
            "通义听悟·会议纪要服务": "待添加"
        }

        # 检查并更新服务状态并创建对应模块
        self.check_and_update_services_status()
        ai_model_section = self.create_ai_model_section()
        main_layout.addLayout(ai_model_section)

        #获取模型攻略按钮
        model_strategy_button = self.create_model_strategy_button()
        main_layout.addWidget(model_strategy_button)

    def create_ai_model_section(self):
        #ai大模型以及配置按钮
        ai_model_layout = QVBoxLayout()
        # ai_model_layout.setSpacing(10)
        ai_model_layout.setContentsMargins(10, 10, 10, 10)

        header_layout = QHBoxLayout()
        ai_model_label = QLabel("AI大模型")
        ai_model_label.setStyleSheet("font-size: 16px; color: black;")
        self.configure_button = QPushButton("配置")

        self.configure_button.setStyleSheet("font-size: 16px;color: #2e8ff4;font-weight: bold;border: none;")
        self.configure_button.setFixedWidth(60)

        header_layout.addWidget(ai_model_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.configure_button)
        header_layout.setContentsMargins(20,20,0,0)

        ai_model_layout.addLayout(header_layout)

        services_box = self.create_services_box()
        ai_model_layout.addWidget(services_box)

        return ai_model_layout

    def create_services_box(self):
        #每个AI模型配置对应布局
        services_box = QWidget()
        services_layout = QVBoxLayout(services_box)
        services_layout.setSpacing(10)

        for service, status in self.services_status.items():
            service_item_layout = QHBoxLayout()
            service_label = QLabel(service)
            service_label.setStyleSheet(f"font-size: 14px;color: black; border:none;")
            status_label = QLabel(status)
            self.status_list.append(status_label)
            if status == "待添加":
                status_label.setStyleSheet(f"font-size: 14px;color: #a4a4a4; border:none; font-weight:bold;")
            else:
                status_label.setStyleSheet(f"font-size: 14px;color: #2e8ff4; font-weight:bold; border:none;")
            service_item_layout.addWidget(service_label)
            service_item_layout.addStretch(1)
            service_item_layout.addWidget(status_label)
            services_layout.addLayout(service_item_layout)

        # 外面大框样式
        services_box.setStyleSheet(
            """
            QWidget {
                border: 1px solid lightgray;
                border-radius: 8px;
                padding: 5px;
                background-color: white;
            }
            """
        )
        return services_box

    def update_status(self):
        # 更新服务状态并设置对应颜色
        self.check_and_update_services_status()
        idx = 0
        for service, status in self.services_status.items():
            self.status_list[idx].setText(status)
            if status == "待添加":
                self.status_list[idx].setStyleSheet(f"font-size: 14px;color: #a4a4a4; border:none; font-weight:bold;")
            else:
                self.status_list[idx].setStyleSheet(f"font-size: 14px;color: #2e8ff4; font-weight:bold; border:none;")
            idx = idx + 1

    def create_model_strategy_button(self):
        # 获取模型攻略按钮
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)


        guide_button = QPushButton()
        guide_button.setIcon(QIcon('../../data/icon_strategy.png'))
        guide_button.setIconSize(QSize(24, 24))
        guide_button.setText("获取模型攻略")
        guide_button.setStyleSheet(
            "color: #2e8ff4; font-size: 16px; border:none;"
        )
        guide_button.setFixedSize(guide_button.sizeHint())

        #点击进入对应网页
        guide_button.clicked.connect(self.open_model_guide)

        bottom_layout.setContentsMargins(30, 0, 0, 130)

        bottom_layout.addWidget(guide_button)
        bottom_layout.addStretch(1)  # 将按钮放在布局的左侧
        return bottom_widget

    def check_and_update_services_status(self):
        # 检查百炼-问答绘图服务的API Key是否已配置
        config_manager = ConfigManager()
        if config_manager.get_online_api_key("阿里云百炼"):
            self.services_status["百炼-问答绘图服务"] = "已添加"
        else:
            self.services_status["百炼-问答绘图服务"] = "待添加"

        # 检查通义听悟·会议纪要服务的App Key是否已配置
        if config_manager.get_online_api_key("通义听悟"):
            self.services_status["通义听悟·会议纪要服务"] = "已添加"
        else:
            self.services_status["通义听悟·会议纪要服务"] = "待添加"

    def open_model_guide(self):
        # 打开模型攻略网页
        webbrowser.open("../../ModelGuidePage.html")


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
        
        

# if __name__ == "__main__":
#     import sys
#     from PyQt5.QtWidgets import QApplication
#     app = QApplication(sys.argv)
#     settings_page = SettingsPage()
#     settings_page.show()
#     sys.exit(app.exec_())
