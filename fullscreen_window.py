"""
大屏模式窗口 - 现代化的全屏体验
"""
from PyQt5 import QtGui
from PyQt5.QtCore import QPoint, Qt, QSize, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import (QWidget, QApplication, QLabel, QPushButton, QAction, 
                             QSizePolicy, QVBoxLayout, QHBoxLayout, QSpacerItem, QDesktopWidget)

from config.config_manager import ConfigManager
from ui.page.setting_page import SettingsPage
from ui.page.about_page import AboutPage
from ui.page.apikey_config_page import ApiKeyConfigPage
from main_window import MainWinTitle, SettingMenu, MainWin
from ui.theme_manager import ThemeManager


class FullScreenWindow(QWidget):
    """大屏模式窗口 - 现代化、居中、宽屏"""
    
    def __init__(self):
        super().__init__()
        available_geometry = QApplication.desktop().availableGeometry()
        
        # 大屏模式尺寸 - 宽屏设计
        self.window_width = 1200
        self.window_height = int(available_geometry.height() * 0.85)
        
        # 内容区域宽度（对话区域）
        self.content_width = 900
        
        self.theme_manager = ThemeManager()
        self.init_ui()
        self._is_drag = False
        self.move_DragPosition = QPoint()
        
        # 连接主题切换信号
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
    
    def init_ui(self):
        self.setWindowTitle(ConfigManager().app_config['name'])
        self.setWindowIcon(QIcon(ConfigManager().app_config['logo']))
        self.setObjectName('fullscreen_window')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        self.resize(self.window_width, self.window_height)
        
        # 标题栏
        self.title_bar = self.create_title_bar()
        
        # 主内容区域
        self.mainwin = MainWin(self.content_width, self.window_height - 60)
        
        # 主布局 - 居中内容
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # 左侧留白
        left_spacer = QSpacerItem(
            (self.window_width - self.content_width) // 2, 
            10, 
            QSizePolicy.Fixed, 
            QSizePolicy.Minimum
        )
        content_layout.addItem(left_spacer)
        
        # 中间内容区域
        content_layout.addWidget(self.mainwin)
        
        # 右侧留白
        right_spacer = QSpacerItem(
            (self.window_width - self.content_width) // 2, 
            10, 
            QSizePolicy.Fixed, 
            QSizePolicy.Minimum
        )
        content_layout.addItem(right_spacer)
        
        # 整体布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        main_layout.addWidget(content_container)
        self.setLayout(main_layout)
        
        # 关于与设置页面
        self.aboutPage = AboutPage(self)
        self.settingPage = SettingsPage(self)
        self.configPage = ApiKeyConfigPage(self)
        
        self.move_to_center()
    
    def create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setFixedHeight(60)
        title_bar.setStyleSheet("background: transparent;")
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 10, 20, 10)
        
        # Logo和标题
        icon_label = QLabel()
        icon_label.setFixedSize(32, 32)
        icon_label.setScaledContents(True)
        icon_label.setPixmap(QPixmap(ConfigManager().app_config['logo']))
        
        title_label = QLabel(ConfigManager().app_config['name'])
        colors = self.theme_manager.get_colors()
        title_label.setStyleSheet(f"""
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI";
            font-weight: 600;
            font-size: 18px;
            color: {colors['title_text']};
        """)
        
        title_layout.addWidget(icon_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 模式切换按钮
        self.mode_switch_btn = QPushButton("切换到侧边栏模式")
        self.mode_switch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 6px;
                padding: 8px 16px;
                color: {colors['button_text']};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
            }}
        """)
        self.mode_switch_btn.clicked.connect(self.switch_to_sidebar)
        title_layout.addWidget(self.mode_switch_btn)
        
        # 设置按钮
        self.setting_btn = QPushButton()
        self.setting_btn.setIcon(QIcon('ui/icon/icon_标题栏_更多.png'))
        self.setting_btn.setIconSize(QSize(24, 24))
        self.setting_btn.setFixedSize(32, 32)
        self.setting_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
            }}
            QPushButton::menu-indicator {{ image: none; }}
        """)
        
        # 设置菜单
        menu = SettingMenu()
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
        
        title_layout.addWidget(self.setting_btn)
        
        # 最小化按钮
        minimize_btn = QPushButton()
        minimize_btn.setIcon(QIcon('ui/icon/icon_标题栏_最小化.png'))
        minimize_btn.setIconSize(QSize(24, 24))
        minimize_btn.setFixedSize(32, 32)
        minimize_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
            }}
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        # 关闭按钮
        close_btn = QPushButton()
        close_btn.setIcon(QIcon('ui/icon/icon_标题栏_关闭.png'))
        close_btn.setIconSize(QSize(24, 24))
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background: #e74c3c;
                border-color: #c0392b;
            }}
        """)
        close_btn.clicked.connect(self.close_window)
        title_layout.addWidget(close_btn)
        
        return title_bar
    
    def switch_to_sidebar(self):
        """切换到侧边栏模式"""
        # 这个方法会在主应用中被重写
        pass
    
    def close_window(self):
        """关闭窗口"""
        self.hide()
    
    def move_to_center(self):
        """将窗口移动到屏幕中央"""
        screen_geometry = QApplication.desktop().availableGeometry()
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
    
    def show_config_page(self):
        """显示配置页面"""
        self.configPage.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.configPage.show()
        self.configPage.raise_()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.configPage.move_to_center()
        self.show()
    
    def show_about_page(self):
        """显示关于页面"""
        self.aboutPage.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.aboutPage.raise_()
        self.aboutPage.move_to_center()
        self.aboutPage.show()
    
    def on_theme_changed(self, theme_name):
        """主题切换回调"""
        self.update()
        # 更新标题栏样式
        colors = self.theme_manager.get_colors()
        self.mode_switch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 6px;
                padding: 8px 16px;
                color: {colors['button_text']};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
            }}
        """)
    
    def paintEvent(self, event):
        """绘制窗口背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 根据主题获取背景颜色
        colors = self.theme_manager.get_colors()
        bg_color = colors['window_bg']
        
        # 使用纯色带圆角
        path = QPainterPath()
        rect = QRectF(self.rect())
        path.addRoundedRect(rect, 16, 16)
        painter.fillPath(path, QColor(bg_color))
    
    def mousePressEvent(self, event):
        """鼠标按下事件 - 用于拖动窗口"""
        if event.button() == Qt.LeftButton:
            self._is_drag = True
            self.move_DragPosition = event.globalPos() - self.pos()
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self._is_drag = False
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖动窗口"""
        self.setCursor(Qt.ArrowCursor)
        if Qt.LeftButton and self._is_drag:
            self.move(event.globalPos() - self.move_DragPosition)
            event.accept()

