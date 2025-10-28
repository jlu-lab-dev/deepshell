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
from ui.utils import ViewMode
from ui.theme_manager import ThemeManager


class ShadowWindow(QWidget):
    def __init__(self):
        super().__init__()
        available_geometry = QApplication.desktop().availableGeometry()
        self.shadow_win_width = 480
        self.shadow_win_height = int(available_geometry.height() * 0.75)

        self.select_icon = QIcon('ui/icon/menu_select.png')
        self.empty_icon = QIcon()
        self.theme_manager = ThemeManager()
        self.current_view_mode = None
        
        self.fullscreen_window = None

        self.grip_size = 8
        self._is_resizing = False
        self._resize_grip = None
        self.grips = {}
        self.cursors = {
            "top_left": Qt.SizeFDiagCursor, "top_right": Qt.SizeBDiagCursor,
            "bottom_left": Qt.SizeBDiagCursor, "bottom_right": Qt.SizeFDiagCursor,
            "top": Qt.SizeVerCursor, "bottom": Qt.SizeVerCursor,
            "left": Qt.SizeHorCursor, "right": Qt.SizeHorCursor,
        }

        self.init_ui()
        self._is_drag = False
        self.move_DragPosition = QPoint()
        
        # 连接主题切换信号
        self.theme_manager.theme_changed.connect(self.on_theme_changed)

        self.theme_manager.theme_changed.connect(self.on_theme_changed)
        self.mainwin.handle_function_selection("智能助手")

    def init_ui(self):
        self.setWindowTitle(ConfigManager().app_config['name'])
        self.setWindowIcon(QIcon(ConfigManager().app_config['logo']))
        self.setObjectName('shadow_window')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
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
        self.setMouseTracking(True)

        # ... (UI 初始化代码的其余部分保持不变) ...
        # 标题中间的文字
        self.middle_label = QLabel()
        self.middle_label.setStyleSheet("""
            font-family: Microsoft YaHei;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
        """)
        self.middle_label.setAlignment(Qt.AlignCenter)
        self.middle_label.setText("智能助手")
        self.middle_label.hide()

        # 语音按钮
        self.speech_button = QPushButton()
        self.speech_button.setFixedSize(24, 24)
        self.speech_button.setFlat(True)
        self.speech_button.setStyleSheet("QPushButton{background-color: transparent;border:none;color:white;}")
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
        self.action_sidebar = QAction("侧边栏模式")
        self.action_sidebar.triggered.connect(lambda: self.switch_view_mode(ViewMode.SIDEBAR))
        sub_menu.addAction(self.action_sidebar)
        self.action_window = QAction("大屏模式")
        self.action_window.triggered.connect(lambda: self.switch_to_fullscreen())
        sub_menu.addAction(self.action_window)
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
        menu.addAction("历史对话", self.show_config_page)
        menu.addAction("模型配置", self.show_config_page)
        menu.addAction("记忆管理", self.show_config_page)
        menu.addSeparator()
        menu.addAction("关于", self.show_about_page)
        self.setting_btn.setMenu(menu)

        # 关闭按钮
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setStyleSheet("QPushButton{background-color:transparent;border:none;color:white;}")
        self.close_btn.setIcon(QIcon('ui/icon/icon_标题栏_关闭.png'))
        self.close_btn.setIconSize(QSize(24, 24))
        self.close_btn.clicked.connect(self.main_window_close)
        # 标题
        self.title = MainWinTitle(title_height=48, parent=self)
        self.title.title_layout.addItem(QSpacerItem(100, 50, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.title.title_layout.insertWidget(3, self.middle_label)
        self.title.title_layout.addWidget(self.speech_button)
        self.title.title_layout.addWidget(self.setting_btn)
        self.title.title_layout.addWidget(self.close_btn)
        # 主窗口
        self.mainwin = MainWin(self.shadow_win_width, self.shadow_win_height - self.title.title_height)
        self.mainwin.title_change_requested.connect(self.change_title_midlabel)
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

        self.switch_view_mode(ViewMode.SIDEBAR)
    
    def switch_to_fullscreen(self):
        """切换到大屏模式（FullScreenWindow）"""
        # 懒加载 FullScreenWindow
        if self.fullscreen_window is None:
            from fullscreen_window import FullScreenWindow
            self.fullscreen_window = FullScreenWindow()
            # 连接大屏窗口的切换回侧边栏的信号
            self.fullscreen_window.switch_to_sidebar = self.switch_from_fullscreen_to_sidebar
        
        # 隐藏当前的shadow window
        self.hide()
        
        # 显示fullscreen window
        self.fullscreen_window.show()
        self.fullscreen_window.raise_()
        self.fullscreen_window.activateWindow()
    
    def switch_from_fullscreen_to_sidebar(self):
        """从大屏模式切换回侧边栏模式"""
        if self.fullscreen_window:
            self.fullscreen_window.hide()
        
        # 确保切换到侧边栏模式
        self.switch_view_mode(ViewMode.SIDEBAR)
        self.show()
        self.raise_()
        self.activateWindow()

    # MODIFIED: 整个函数被重构以正确处理尺寸限制
    def switch_view_mode(self, mode: ViewMode):
        """统一的视图模式切换函数"""
        if self.current_view_mode == mode:
            return

        self.current_view_mode = mode
        self.update_menu_icon_state(mode)

        self.mainwin.chat_box.switchViewType(mode)
        self.mainwin.speech_page.switchViewType(mode)
        self.mainwin.meetingWgt.switchViewType(mode)
        self.mainwin.meeting_bottom_ui.switchViewType(mode)
        self.title.switchViewType(mode)

        if mode == ViewMode.SIDEBAR:
            # --- 侧边栏模式逻辑 ---
            # 1. 设置窗口标志位
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)

            # 2. 移除窗口模式下的尺寸限制
            # 必须先解除最大/最小尺寸限制，才能设置固定尺寸
            QSS_MAX_SIZE = 16777215  # Qt的默认最大值
            self.setMinimumSize(0, 0)
            self.setMaximumSize(QSS_MAX_SIZE, QSS_MAX_SIZE)

            # 3. 设置固定的尺寸
            self.setFixedSize(self.shadow_win_width, self.shadow_win_height)
            self.mainwin.setFixedSize(self.shadow_win_width, self.shadow_win_height - self.title.title_height)

            # 4. 移动到目标位置
            self.move_to_right_bottom()

        elif mode == ViewMode.WINDOW:
            # --- 窗口模式逻辑 ---
            # 1. 设置窗口标志位
            self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

            # 2. 解除侧边栏模式下的固定尺寸限制
            # 必须先解除固定尺寸，才能设置最小/最大尺寸
            self.setFixedSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)  # Helper constant for max size
            self.mainwin.setFixedSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)

            # 3. 设置新的尺寸限制和初始大小
            self.setMinimumSize(600, 800)
            desktop_size = QDesktopWidget().screenGeometry()
            self.setMaximumSize(desktop_size.width(), desktop_size.height())
            self.resize(1200, 900)

            # 4. 移动到屏幕中央
            self.move_to_center()

        self.show()
        self.raise_()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        colors = self.theme_manager.get_colors()
        bg_color = colors['window_bg']
        path = QPainterPath()
        rect = QRectF(self.rect())
        path.addRoundedRect(rect, 16, 16)
        painter.fillPath(path, QColor(bg_color))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.current_view_mode == ViewMode.WINDOW and self._resize_grip:
                self._is_resizing = True
                self.move_DragPosition = event.globalPos()
                event.accept()
            elif self.title.geometry().contains(event.pos()):
                self._is_drag = True
                self.move_DragPosition = event.globalPos() - self.pos()
                event.accept()

    def mouseMoveEvent(self, event):
        if self.current_view_mode == ViewMode.WINDOW and not self._is_drag and not self._is_resizing:
            self.update_grips()
            changed_cursor = False
            for grip, rect in self.grips.items():
                if rect.contains(event.pos()):
                    self.setCursor(self.cursors[grip])
                    self._resize_grip = grip
                    changed_cursor = True
                    break
            if not changed_cursor:
                self.setCursor(Qt.ArrowCursor)
                self._resize_grip = None

        if self._is_drag:
            self.move(event.globalPos() - self.move_DragPosition)
            event.accept()
        elif self._is_resizing:
            delta = event.globalPos() - self.move_DragPosition
            self.move_DragPosition = event.globalPos()
            geom = self.geometry()

            if "top" in self._resize_grip: geom.setTop(geom.top() + delta.y())
            if "bottom" in self._resize_grip: geom.setBottom(geom.bottom() + delta.y())
            if "left" in self._resize_grip: geom.setLeft(geom.left() + delta.x())
            if "right" in self._resize_grip: geom.setRight(geom.right() + delta.x())

            if geom.width() < self.minimumWidth(): geom.setWidth(self.minimumWidth())
            if geom.height() < self.minimumHeight(): geom.setHeight(self.minimumHeight())

            self.setGeometry(geom)

    def mouseReleaseEvent(self, event):
        self._is_drag = False
        self._is_resizing = False
        self._resize_grip = None
        self.setCursor(Qt.ArrowCursor)

    def update_grips(self):
        self.grips = {
            "top_left": QRectF(0, 0, self.grip_size, self.grip_size),
            "top_right": QRectF(self.width() - self.grip_size, 0, self.grip_size, self.grip_size),
            "bottom_left": QRectF(0, self.height() - self.grip_size, self.grip_size, self.grip_size),
            "bottom_right": QRectF(self.width() - self.grip_size, self.height() - self.grip_size, self.grip_size,
                                   self.grip_size),
            "top": QRectF(self.grip_size, 0, self.width() - 2 * self.grip_size, self.grip_size),
            "bottom": QRectF(self.grip_size, self.height() - self.grip_size, self.width() - 2 * self.grip_size,
                             self.grip_size),
            "left": QRectF(0, self.grip_size, self.grip_size, self.height() - 2 * self.grip_size),
            "right": QRectF(self.width() - self.grip_size, self.grip_size, self.grip_size,
                            self.height() - 2 * self.grip_size),
        }

    # ... (其余所有辅助函数保持不变) ...
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
        return QDesktopWidget().availableGeometry()

    def move_to_right_bottom(self):
        screen_geometry = self.get_primary_screen_geometry()
        frame_geo = self.frameGeometry()
        x = screen_geometry.right() - frame_geo.width()
        y = screen_geometry.bottom() - frame_geo.height()
        self.move(x, y)

    def move_to_center(self):
        screen_geo = self.get_primary_screen_geometry()
        frame_geo = self.frameGeometry()
        pos = QPoint(
            int((screen_geo.width() - frame_geo.width()) / 2),
            int((screen_geo.height() - frame_geo.height()) / 2)
        )
        self.move(pos)

    def update_menu_icon_state(self, mode: ViewMode):
        if mode == ViewMode.SIDEBAR:
            self.action_sidebar.setIcon(self.select_icon)
            self.action_window.setIcon(self.empty_icon)
        elif mode == ViewMode.WINDOW:
            self.action_sidebar.setIcon(self.empty_icon)
            self.action_window.setIcon(self.select_icon)

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
        if text == "系统功能": text = "智能助手"
        if text == "智能助手":
            pass
        else:
            self.middle_label.setText(text.upper())
            self.middle_label.show()

    def icon_clicked_event(self):
        self.mainwin.handle_function_selection("智能助手")
        self.middle_label.hide()

    def main_window_close(self):
        self.window_visible = False
        self.hide()

    def on_theme_changed(self, theme_name):
        self.update()

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        if a0.key() == Qt.Key_Escape:
            self.mainwin.shift2home_page()


# A small helper constant for setFixedSize
QWIDGETSIZE_MAX = 16777215