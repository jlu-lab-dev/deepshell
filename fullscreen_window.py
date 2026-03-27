"""
大屏模式窗口 - 现代化的全屏体验
"""
from PyQt5 import QtGui
from PyQt5.QtCore import QPoint, Qt, QSize, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath
from PyQt5.QtWidgets import (QWidget, QApplication, QLabel, QPushButton, QAction, 
                             QSizePolicy, QVBoxLayout, QHBoxLayout, QSpacerItem, 
                             QDesktopWidget, QGraphicsDropShadowEffect, QFileDialog)

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
        
        # 大屏模式尺寸
        self.window_width = 1200
        self.window_height = int(available_geometry.height() * 0.70)
        
        # 内容区域宽度（对话区域）
        self.content_width = 850
        
        # 侧边栏宽度（对话历史）
        self.sidebar_width = 220
        
        self.theme_manager = ThemeManager()
        self.init_ui()
        self._is_drag = False
        self.move_DragPosition = QPoint()

        self.mainwin.title_change_requested.connect(self.update_main_title)
        # 连接主题切换信号
        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        if hasattr(self, 'mainwin') and self.mainwin:
            self.mainwin.handle_function_selection("智能问答")
    
    def init_ui(self):
        self.setWindowTitle(ConfigManager().app_config['name'])
        self.setWindowIcon(QIcon(ConfigManager().app_config['logo']))
        self.setObjectName('fullscreen_window')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        # 设置固定尺寸，防止内容撑大窗口
        self.setFixedSize(self.window_width, self.window_height)
        
        # 标题栏
        self.title_bar = self.create_title_bar()
        
        # 左侧对话历史
        self.sidebar = self.create_sidebar()
        
        # 主内容区域
        self.mainwin = MainWin(self.content_width, self.window_height - 80)
        self.mainwin.setMaximumHeight(self.window_height - 80)
        
        # 主布局 - 内容区域
        content_container = QWidget()
        content_container.setObjectName('content_container')
        colors = self.theme_manager.get_colors()
        content_container.setStyleSheet(f"""
            QWidget#content_container {{
                background: {colors['window_bg']};
                border-radius: 0px;
            }}
        """)
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(20, 10, 20, 20)
        content_layout.setSpacing(15)
        
        # 左侧边栏
        content_layout.addWidget(self.sidebar)
        
        # 主内容
        content_layout.addWidget(self.mainwin)
        
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
    
    def create_sidebar(self):
        """创建对话历史侧边栏"""
        colors = self.theme_manager.get_colors()
        
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(self.sidebar_width)
        sidebar.setStyleSheet(f"""
            QWidget#sidebar {{
                background: transparent;
            }}
        """)
        
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 10, 8, 10)
        sidebar_layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("对话")
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {colors['button_text']};
                font-size: 15px;
                font-weight: bold;
                padding: 5px 8px;
            }}
        """)
        sidebar_layout.addWidget(title_label)
        
        # 新建对话按钮
        new_chat_btn = QPushButton("+ 新对话")
        new_chat_btn.setCursor(Qt.PointingHandCursor)
        new_chat_btn.setFixedHeight(38)
        new_chat_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 8px;
                color: {colors['button_text']};
                font-size: 13px;
                font-weight: 600;
                padding: 6px 10px;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 1px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors['button_pressed']};
            }}
        """)
        sidebar_layout.addWidget(new_chat_btn)
        
        # 分隔线
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background: {colors['button_border']};")
        sidebar_layout.addWidget(separator)
        
        # Mock 对话历史记录
        from PyQt5.QtWidgets import QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {colors['scrollbar_handle']};
                border-radius: 3px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {colors['scrollbar_handle_hover']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background: {colors['window_bg']};")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(4)
        
        # Mock 数据 - 对话历史
        mock_sessions = [
            ("今天", "DNS 网络配置"),
            ("今天", "Domain and Mapper Code"),
            ("本周", "批量处理文件"),
            ("本周", "内存占用量大的进程管理"),
            ("本周", "3月4月工作计划总结"),
            ("更早", "国产操作系统换装问题"),
            ("更早", "Git 版本控制"),
        ]
        
        current_time_group = None
        for time_group, title in mock_sessions:
            # 显示时间分组
            if time_group != current_time_group:
                current_time_group = time_group
                time_label = QLabel(time_group)
                time_label.setStyleSheet(f"""
                    QLabel {{
                        color: {colors['input_placeholder']};
                        font-size: 12px;
                        padding: 8px 8px 4px 8px;
                    }}
                """)
                scroll_layout.addWidget(time_label)
            
            # 对话项按钮
            session_btn = QPushButton(title)
            session_btn.setCursor(Qt.PointingHandCursor)
            session_btn.setFixedHeight(36)
            session_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                    color: {colors['button_text']};
                    font-size: 13px;
                    padding: 8px 10px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background: {colors['button_hover']};
                    border: 1px solid {colors['button_border']};
                }}
                QPushButton:pressed {{
                    background: {colors['button_pressed']};
                }}
            """)
            scroll_layout.addWidget(session_btn)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        sidebar_layout.addWidget(scroll_area)
        
        return sidebar
    
    def create_title_bar(self):
        """创建标题栏 - 现代化设计"""
        title_bar = QWidget()
        title_bar.setFixedHeight(60)
        title_bar.setStyleSheet("background: transparent;")
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(30, 10, 30, 10)
        title_layout.setSpacing(12)
        
        # Logo和标题容器 - 带光晕效果
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(12)
        
        # Logo
        icon_label = QLabel()
        icon_label.setFixedSize(36, 36)
        icon_label.setScaledContents(True)
        icon_label.setPixmap(QPixmap(ConfigManager().app_config['logo']))
        
        # 标题 - 带渐变文字效果
        self.title_label = QLabel(ConfigManager().app_config['name'])
        colors = self.theme_manager.get_colors()
        self.title_label.setStyleSheet(f"""
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC";
                font-weight: 700;
                font-size: 20px;
                color: {colors['title_text']};
                letter-spacing: 0.5px;
            """)

        logo_layout.addWidget(icon_label)
        logo_layout.addWidget(self.title_label)
        
        title_layout.addWidget(logo_container)
        title_layout.addStretch()
        
        # 打开文件按钮
        self.open_file_btn = QPushButton("📁 打开文件")
        self.open_file_btn.setFixedHeight(36)
        self.open_file_btn.setCursor(Qt.PointingHandCursor)
        self.open_file_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
                padding: 0px 16px;
                color: {colors['button_text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 2px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors['button_pressed']};
            }}
        """)
        self.open_file_btn.clicked.connect(self.open_file_dialog)
        title_layout.addWidget(self.open_file_btn)
        
        # 模式切换按钮 - 渐变按钮设计
        self.mode_switch_btn = QPushButton("◀ 侧边栏模式")
        self.mode_switch_btn.setFixedHeight(36)
        self.mode_switch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
                padding: 0px 20px;
                color: {colors['button_text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 2px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors['button_pressed']};
            }}
        """)
        self.mode_switch_btn.clicked.connect(self.switch_to_sidebar)
        title_layout.addWidget(self.mode_switch_btn)
        
        # 设置按钮 - 圆形设计
        self.setting_btn = QPushButton()
        self.setting_btn.setIcon(QIcon('ui/icon/icon_标题栏_更多.png'))
        self.setting_btn.setIconSize(QSize(20, 20))
        self.setting_btn.setFixedSize(36, 36)
        self.setting_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 2px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors['button_pressed']};
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
        
        # 最小化按钮 - 圆形设计
        minimize_btn = QPushButton()
        minimize_btn.setIcon(QIcon('ui/icon/DeepShell/最小化.png'))
        minimize_btn.setIconSize(QSize(20, 20))
        minimize_btn.setFixedSize(36, 36)
        minimize_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background: #f39c12;
                border: 2px solid #e67e22;
            }}
            QPushButton:pressed {{
                background: #e67e22;
            }}
        """)
        minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        # 关闭按钮 - 圆形设计，红色悬浮效果
        close_btn = QPushButton()
        close_btn.setIcon(QIcon('ui/icon/icon_标题栏_关闭.png'))
        close_btn.setIconSize(QSize(20, 20))
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #e74c3c, stop:1 #c0392b);
                border: 2px solid #c0392b;
            }}
            QPushButton:pressed {{
                background: #c0392b;
            }}
        """)
        close_btn.clicked.connect(self.close_window)
        title_layout.addWidget(close_btn)
        
        return title_bar
    
    def open_file_dialog(self):
        """打开文件选择对话框"""
        import subprocess
        import os
        
        options = QFileDialog.Options()
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要打开的文件",
            os.path.expanduser("~"),  # 从用户主目录开始
            "所有文件 (*);;文档 (*.pdf *.docx *.txt *.md);;图片 (*.png *.jpg *.jpeg);;音频 (*.mp3 *.m4a *.wav);;表格 (*.csv *.xlsx)",
            options=options
        )
        
        if file_paths:
            for file_path in file_paths:
                try:
                    # 在Mac上使用open命令打开文件
                    subprocess.run(['open', file_path], check=True)
                except Exception as e:
                    print(f"打开文件失败: {file_path}, 错误: {e}")
    
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
        """主题切换回调 - 更新所有组件样式"""
        colors = self.theme_manager.get_colors()
        
        # 更新打开文件按钮
        self.open_file_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
                padding: 0px 16px;
                color: {colors['button_text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 2px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors['button_pressed']};
            }}
        """)
        
        # 更新模式切换按钮
        self.mode_switch_btn.setStyleSheet(f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 2px solid {colors['button_border']};
                border-radius: 18px;
                padding: 0px 20px;
                color: {colors['button_text']};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 2px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors['button_pressed']};
            }}
        """)
        
        # 侧边栏在主题切换时会自动更新（因为使用了动态colors变量）
        # 无需额外处理
        
        # 重新绘制窗口以应用渐变背景
        self.update()
    
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
        path.addRoundedRect(rect, 20, 20)
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

    def update_main_title(self, text: str):
        """Slot to handle title change requests from MainWin."""
        if text == "系统功能" or text == "智能问答":
            # In fullscreen mode, revert to the app's main name for the home function
            self.title_label.setText(ConfigManager().app_config['name'])
        else:
            self.title_label.setText(text.upper())