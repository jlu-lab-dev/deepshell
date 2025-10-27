from PyQt5 import QtGui
from PyQt5.QtCore import QPoint, Qt, QSize, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QPushButton, QAction, QSizePolicy, QVBoxLayout, QSpacerItem, \
    QDesktopWidget

from config.config_manager import ConfigManager
from ui.page.setting_page import SettingsPage
from ui.page.about_page import AboutPage
from ui.page.apikey_config_page import ApiKeyConfigPage
from main_window import MainWinTitle, SettingMenu
from main_window import MainWin
from ui.theme_manager import ThemeManager


class ShadowWindow(QWidget):
    def __init__(self):
        super().__init__()
        available_geometry = QApplication.desktop().availableGeometry()
        # 窗口尺寸 - 稍微窄一点，高度为屏幕的90%
        self.shadow_win_width = 450
        self.shadow_win_height = int(available_geometry.height() * 0.9)
        self.theme_manager = ThemeManager()
        self.init_ui()
        self._is_drag = False  # 拖动
        self.move_DragPosition = QPoint()
        
        # 连接主题切换信号
        self.theme_manager.theme_changed.connect(self.on_theme_changed)

    def init_ui(self):
        self.setWindowTitle(ConfigManager().app_config['name'])
        self.setWindowIcon(QIcon(ConfigManager().app_config['logo']))
        self.setObjectName('shadow_window')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)  # Qt.Dialog主要用于在任务栏隐藏图标
        self.setStyleSheet(
            '''
            #shadowindow{
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 15px;
            }
            '''
        )
        self.resize(self.shadow_win_width, self.shadow_win_height)

        # 标题中间的文字
        self.middle_label = QLabel()   # 中间的标签
        self.middle_label.setStyleSheet("""
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
        """)
        self.middle_label.setAlignment(Qt.AlignCenter)
        self.middle_label.setText("智能问答")
        self.middle_label.hide()  # 初始状态隐藏，当后面点击窗口的时候进行显示

        # 语音按钮
        self.speech_button = QPushButton()
        self.speech_button.setFixedSize(24, 24)
        self.speech_button.setFlat(True)
        self.speech_button.setStyleSheet(
            '''
            QPushButton{background-color: transparent;border:none;color:white;}
            '''
        )
        self.speech_button.setIcon(QIcon('ui/icon/icon_标题栏_麦克风.png'))
        self.speech_button.setIconSize(QSize(24, 24))
        self.speech_button.clicked.connect(self.switch2speech)

        # 设置按钮
        self.setting_btn = QPushButton()
        self.setting_btn.setIcon(QIcon('ui/icon/icon_标题栏_更多.png'))
        self.setting_btn.setIconSize(QSize(24, 24))
        self.setting_btn.setFixedSize(24, 24)
        self.setting_btn.setStyleSheet(
            '''
            QPushButton{background-color:transparent;border:none;color:white;}
            QPushButton::menu-indicator { image: none; }
            '''
        )

        # 为设置按钮添加二级菜单
        menu = SettingMenu()
        sub_menu = menu.addMenu("显示模式")
        self.action_sidebar = QAction(QIcon('ui/icon/menu_select.png'), "侧边栏模式")
        self.action_sidebar.triggered.connect(self.switchToSidebar)
        sub_menu.addAction(self.action_sidebar)
        menu.sub_menu = sub_menu
        menu.setSubMenu()

        # 添加主题切换选项
        theme_menu = menu.addMenu("主题")
        self.action_dark = QAction("深色主题")
        self.action_dark.triggered.connect(lambda: self.theme_manager.set_theme('dark'))
        self.action_light = QAction("浅色主题")
        self.action_light.triggered.connect(lambda: self.theme_manager.set_theme('light'))
        theme_menu.addAction(self.action_dark)
        theme_menu.addAction(self.action_light)
        
        menu.addAction("配置", self.show_config_page)
        menu.addSeparator()
        menu.addAction("关于", self.show_about_page)
        self.setting_btn.setMenu(menu)

        # 关闭按钮
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet(
            '''
            QPushButton{background-color:transparent;border:none;color:white;}
            '''
        )
        self.close_btn.setIcon(QIcon('ui/icon/icon_标题栏_关闭.png'))
        self.close_btn.setIconSize(QSize(24, 24))
        self.close_btn.clicked.connect(self.main_window_close)
        self.close_btn.setFixedSize(24, 24)

        # 标题
        self.title = MainWinTitle(title_height=48)
        self.title.title_layout.addItem(
            QSpacerItem(100, 50, QSizePolicy.Expanding, QSizePolicy.Minimum))  # 将弹性空间添加到布局中，确保其居中
        self.title.title_layout.insertWidget(3, self.middle_label)
        self.title.title_layout.addWidget(self.speech_button)
        self.title.title_layout.addWidget(self.setting_btn)
        self.title.title_layout.addWidget(self.close_btn)

        # 主窗口
        self.mainwin = MainWin(self.shadow_win_width, self.shadow_win_height - self.title.title_height)
        self.mainwin.chat_box.update()
        self.mainwin.chat_box.set_scroll_bar_value(200)

        # 界面布局
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.title)
        layout.addWidget(self.mainwin)
        self.setLayout(layout)

        # 关于与设置页面
        self.aboutPage = AboutPage(self)
        self.settingPage = SettingsPage(self)
        self.configPage = ApiKeyConfigPage(self)

        self.switchToSidebar()
        self.move_to_right_bottom()

    # 切换功能跳转函数
    def switch2speech(self):
        if self.mainwin.speech_page.isHidden():
            self.mainwin.handle_function_selection("语音聊天")
            self.middle_label.hide()
            self.mainwin.chat_box.hide()
            self.mainwin.input_field.hide()
            self.mainwin.function_menu_btn.hide()
            self.mainwin.new_dialog_btn.hide()
            self.mainwin.meetingWgt.hide()
            self.mainwin.meeting_bottom_ui.hide()
            self.mainwin.knowledge_base_select_btn.hide()
            self.mainwin.model_select_btn.hide()
        else:
            self.mainwin.shift2home_page()

    def get_primary_screen_geometry(self):
        """获取主屏幕的几何信息"""
        desktop = QDesktopWidget()
        screen_count = desktop.screenCount()
        if screen_count > 1:
            # 多屏幕情况下，使用第一块屏幕
            return desktop.availableGeometry(0)
        else:
            # 单屏幕情况下，使用默认屏幕
            return desktop.availableGeometry()

    def move_to_right_bottom(self):
        """将窗口移动到屏幕的右下角"""
        screen_geometry = self.get_primary_screen_geometry()

        # 计算窗口的新位置
        x = screen_geometry.right() - self.width()
        y = screen_geometry.bottom() - self.height()
        self.move(x, y)

    def move_to_center(self):
        """将窗口移动到屏幕的中间"""
        screen_geometry = self.get_primary_screen_geometry()

        # 计算窗口的新位置
        x = screen_geometry.width() / 2 - self.width() / 2
        y = screen_geometry.height() / 2 - self.height() / 2
        self.move(x, y)

    # 切换到侧边栏模式
    def switchToSidebar(self):
        self.mainwin.chat_box.switchViewType()
        self.mainwin.speech_page.switchViewType()
        self.mainwin.meetingWgt.switchViewType()
        self.mainwin.meeting_bottom_ui.switchViewType()

        self.mainwin.setMaximumHeight(self.shadow_win_height - self.title.title_height)
        self.mainwin.resize(self.shadow_win_width, self.shadow_win_height - self.title.title_height)

        self.title.switchViewType()

        self.setMaximumHeight(self.shadow_win_height)
        self.setMaximumWidth(self.shadow_win_width)
        self.resize(self.shadow_win_width, self.shadow_win_height)

        self.move_to_right_bottom()
        self.show()
        self.raise_()
        self.activateWindow()

    def show_config_page(self):
        self.configPage.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.configPage.show()
        self.configPage.raise_()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.configPage.move_to_center()
        self.show()

    def show_about_page(self):
        self.aboutPage.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.aboutPage.raise_()
        self.aboutPage.move_to_center()
        self.aboutPage.show()

    def change_title_midlabel(self, text):
        self.middle_label.setText(text.upper())
        self.middle_label.show()

    def icon_clicked_event(self):
        self.mainwin.handle_function_selection("智能问答")
        self.middle_label.hide()

    def main_window_close(self):
        self.window_visible = False
        self.hide()

    def on_theme_changed(self, theme_name):
        """主题切换时的回调"""
        self.update()  # 重绘窗口
    
    # 重写原有方法 Start
    def paintEvent(self, event):
        # 创建一个QPainter对象，并为当前窗口提供绘图功能
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
        
        # 根据主题获取背景颜色
        colors = self.theme_manager.get_colors()
        bg_color = colors['window_bg']
        
        # 使用纯色带圆角
        path = QPainterPath()
        rect = QRectF(self.rect())
        path.addRoundedRect(rect, 16, 16)  # 16px圆角 - 更加圆润
        painter.fillPath(path, QColor(bg_color))

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        if a0.key() == Qt.Key_Escape:
            self.mainwin.shift2home_page()

    def mousePressEvent(self, event):
        # 重写鼠标点击的事件
        if event.button() == Qt.LeftButton:
            # 鼠标左键点击标题栏区域
            self._is_drag = True
            self.move_DragPosition = event.globalPos() - self.pos()
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_drag = False

    def mouseMoveEvent(self, event):
        # 判断鼠标位置切换鼠标手势
        self.setCursor(Qt.ArrowCursor)
        if Qt.LeftButton and self._is_drag:
            # 标题栏拖放窗口位置
            self.move(event.globalPos() - self.move_DragPosition)
            event.accept()
    # 重写原有方法 End