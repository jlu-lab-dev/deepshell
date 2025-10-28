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
        # 窗口尺寸 - 稍微窄一点，高度为屏幕的90%
        self.shadow_win_width = 480
        self.shadow_win_height = int(available_geometry.height() * 0.75)

        # NEW: 提前加载好“选中”和“空”图标
        self.select_icon = QIcon('ui/icon/menu_select.png')
        self.empty_icon = QIcon()

        self.theme_manager = ThemeManager()
        self.current_view_mode = None
        self.init_ui()
        self._is_drag = False  # 拖动
        self.move_DragPosition = QPoint()

        # 连接主题切换信号
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

        # MODIFIED: 创建时不设置图标，后续动态更新
        self.action_sidebar = QAction("侧边栏模式")
        self.action_sidebar.triggered.connect(lambda: self.switch_view_mode(ViewMode.SIDEBAR))
        sub_menu.addAction(self.action_sidebar)

        self.action_window = QAction("窗口模式")
        self.action_window.triggered.connect(lambda: self.switch_view_mode(ViewMode.WINDOW))
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

        menu.addAction("记忆管理", self.show_config_page)
        menu.addAction("配置", self.show_config_page)
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

        # MODIFIED: 调用新的统一函数进行初始化
        self.switch_view_mode(ViewMode.SIDEBAR)

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

    # MODIFIED: 修正为使用 frameGeometry 以精确定位
    def move_to_right_bottom(self):
        """将窗口移动到屏幕的右下角"""
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

    def switch_view_mode(self, mode: ViewMode):
        """统一的视图模式切换函数"""
        if self.current_view_mode == mode:
            return

        self.current_view_mode = mode
        self.update_menu_icon_state(mode)  # NEW: 调用函数更新菜单图标

        self.mainwin.chat_box.switchViewType(mode)
        self.mainwin.speech_page.switchViewType(mode)
        self.mainwin.meetingWgt.switchViewType(mode)
        self.mainwin.meeting_bottom_ui.switchViewType(mode)
        self.title.switchViewType(mode)

        if mode == ViewMode.SIDEBAR:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
            self.mainwin.setMaximumHeight(self.shadow_win_height - self.title.title_height)
            self.mainwin.resize(self.shadow_win_width, self.shadow_win_height - self.title.title_height)

            self.setMaximumHeight(self.shadow_win_height)
            self.setMaximumWidth(self.shadow_win_width)
            self.resize(self.shadow_win_width, self.shadow_win_height)
            self.move_to_right_bottom()

        elif mode == ViewMode.WINDOW:
            self.setWindowFlags(Qt.Window)
            self.setMinimumSize(600, 800)
            desktop_size = QDesktopWidget().screenGeometry()
            self.setMaximumSize(desktop_size.width(), desktop_size.height())
            self.resize(700, 900)
            self.move_to_center()

        self.show()
        self.raise_()
        self.activateWindow()

    # NEW: 新增函数，专门用于更新菜单项的图标状态
    def update_menu_icon_state(self, mode: ViewMode):
        """根据当前的视图模式，更新菜单项的勾选图标"""
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
        if text == "系统功能":
            text = "智能助手"

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        colors = self.theme_manager.get_colors()
        bg_color = colors['window_bg']

        path = QPainterPath()
        rect = QRectF(self.rect())

        if self.current_view_mode == ViewMode.SIDEBAR:
            path.addRoundedRect(rect, 16, 16)
            painter.fillPath(path, QColor(bg_color))
        else:
            painter.fillRect(rect, QColor(bg_color))

    def keyPressEvent(self, a0: QtGui.QKeyEvent) -> None:
        if a0.key() == Qt.Key_Escape:
            self.mainwin.shift2home_page()

    def mousePressEvent(self, event):
        if self.current_view_mode == ViewMode.SIDEBAR and event.button() == Qt.LeftButton:
            if self.title.geometry().contains(event.pos()):
                self._is_drag = True
                self.move_DragPosition = event.globalPos() - self.pos()
                event.accept()

    def mouseReleaseEvent(self, event):
        self._is_drag = False

    def mouseMoveEvent(self, event):
        if self.current_view_mode == ViewMode.SIDEBAR and Qt.LeftButton and self._is_drag:
            self.move(event.globalPos() - self.move_DragPosition)
            event.accept()