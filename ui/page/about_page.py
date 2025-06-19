from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QDesktopWidget
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QPen, QPixmap, QIcon

from ui.page.apikey_config_page import ApiKeyConfigPage
from config.config_manager import ConfigManager

class AboutPage(QWidget):
    def __init__(self, parent=None):
        super(AboutPage, self).__init__(parent)
        layout = QVBoxLayout(self)  # 包含顶栏和主要内容
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint) #Qt.Dialog主要用于在任务栏隐藏图标
        self.resize(450, 350)
        
        # 背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # 顶部栏
        top_bar = self.create_top_bar()
        layout.addWidget(top_bar)
        
        #主要内容
        self.setting_main_window =  AboutMainWindow()
        layout.addWidget(self.setting_main_window)
        
        
        layout.setContentsMargins(0, 0, 0, 0)
        
    def openApiKeyConfigPage(self):
        # 创建并显示 APIKeyConfigPage 窗口
        self.apiKeyConfigPage = ApiKeyConfigPage()
        self.hide()
        self.apiKeyConfigPage.show()
        # 将窗口置顶
        self.apiKeyConfigPage.raise_()
        # self.hide()
           
    def create_top_bar(self):
        setting_page_title = BoxTitle(self)

        #创建顶部栏
        top_bar_layout = QHBoxLayout()

        title_label = QLabel("关于")
        title_label.setStyleSheet("font-size: 16px; color: black;")

        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            '''
            QPushButton{background-color:transparent;border:none;color:white;}
            '''
        )

        close_btn.setIcon(QIcon('ui/icon/icon_关闭_窗口模式@2x.png'))
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


class AboutMainWindow(QWidget):
    # 定义关闭信号
    closed = pyqtSignal()
    def __init__(self, parent=None):
        super(AboutMainWindow, self).__init__(parent)
        self.moving = False
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(50, 20, 50, 50)
        
        #实现圆角
        self.setObjectName('mainwindow')
        self.radius = 10

        # 背景透明
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        
        # 检查并更新服务状态并创建对应模块
        titile_about_section = self.create_titile_about_section()
        main_layout.addLayout(titile_about_section)
        
        titile_about_section = self.create_content_about_section()
        main_layout.addLayout(titile_about_section)


    def create_titile_about_section(self):
        #ai大模型以及配置按钮
        title_layout = QHBoxLayout()
        # ai_model_layout.setSpacing(10)

        word_layout = QVBoxLayout()
        word_label_one = QLabel(f"{ConfigManager().app_config['name']}")
        word_label_one.setStyleSheet("font-size: 16px; color: black;")
        
        word_label_two = QLabel(f"{ConfigManager().app_config['version']}")
        word_label_two.setStyleSheet("font-size: 10px; color: black;")
        
        word_layout.addWidget(word_label_one)
        word_layout.addWidget(word_label_two)
        
        icon_label = QLabel()
        icon_pixmap = QPixmap('../../data/logo_about.png')  # 替换为你的图标文件路径
        icon_label.setPixmap(icon_pixmap)

        title_layout.addLayout(word_layout)
        title_layout.addStretch(1)
        title_layout.addWidget(icon_label)

        return title_layout
    
    def create_content_about_section(self):
        content_layout = QVBoxLayout()
        word_label_one = QLabel(f"{ConfigManager().app_config['name']}{ConfigManager().app_config['description']}")
        
        word_label_one.setStyleSheet("font-size: 14px; color: black;")
        
        content_layout.addWidget(word_label_one)
        return content_layout


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
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    settings_page = AboutPage()
    settings_page.show()
    sys.exit(app.exec_())
