import json

from PyQt5 import QtGui
from PyQt5.QtCore import QPoint, Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QPushButton, QAction, QSizePolicy, QVBoxLayout, QSpacerItem, \
    QDesktopWidget

from config.config_manager import ConfigManager
from ui.page.setting_page import SettingsPage
from ui.page.about_page import AboutPage
from ui.page.apikey_config_page import ApiKeyConfigPage
from main_window import MainWinTitle, SettingMenu
from main_window import MainWin


# app_list = '[{"打开系统设置": "found-control-center"}, {"打开应用商店": "ai-assistant open-appstore"}, {"打开视频播放器": "ai-assistant open-video-player"},  {"打开浏览器": "nfs-browser"},{"打开文本编辑器":"ai-assistant open-txt"}, {"打开日历":"ai-assistant open-calender"},{"调高音量":"ai-assistant  set-volume-up"},{"调低音量":"ai-assistant  set-volume-down"},{"调高屏幕亮度":"ai-assistant  set-brightness-up"},{"调低屏幕亮度":"ai-assistant  set-brightness-down"},{"打开登录密码设置":"ai-assistant set-password"},{"打开屏幕分辨率设置":"ai-assistant set-display"},{"打开默认程序设置":"ai-assistant set-default-apps"},{"打开系统主题设置":"ai-assistant set-theme"},{"打开字体设置":"ai-assistant set-font"},{"打开系统音量设置":"ai-assistant set-sound"},{"打开系统时间设置":"ai-assistant set-datetime"},{"打开节能模式设置":"ai-assistant set-powersave-mode"},{"打开锁屏时间设置":"ai-assistant set-lock"},{"查询系统版本信息":"ai-assistant get-system-info"},{"查询CPU信息":"ai-assistant get-cpu-info"},{"查询内核版本":"ai-assistant get-kernel-info"},{"查询内存信息":"ai-assistant get-memory-info"},{"打开壁纸设置":"ai-assistant set-background"},{"打开网络设置":"ai-assistant set-network"},{"打开屏保设置":"ai-assistant set-screensaver"},{"打开邮箱":"ai-assistant open-email"},{"打开系统帮助":"ai-assistant open-system-help"},{"打开文件管理器":"ai-assistant open-file-manager"},{"打开资源监视器":"ai-assistant open-stacer"},{"打开文档查看器":"ai-assistant open-document-viewer"},{"打开终端":"ai-assistant open-terminal"},{"打开压缩工具":"ai-assistant open-file-compress"},{"打开计算器":"ai-assistant open-calculator"},{"打开wifi设置":"ai-assistant set-wifi"},{"打开蓝牙设置":"ai-assistant set-bluetooth"},{"打开画板":"ai-assistant open-drawing-board"},{"关闭画板":"killall nfs-drawing"},{"关闭应用商店":"ai-assistant close-appstore"},{"关闭视频播放器":"ai-assistant close-video-player"},{"打开音乐播放器":"ai-assistant open-music"},{"关闭音乐播放器":"ai-assistant close-music"},{"关闭文本编辑器":"ai-assistant close-txt"},{"关闭计算器":"ai-assistant close-calculator"},{"关闭系统设置":"killall found-control-center"},{"关闭浏览器":"killall nfs-browser"},{"关闭终端":"killall gnome-terminal-server"},{"关闭资源监视器":"killall stacer"},{"关闭邮箱":"killall thunderbird"},{"关闭wifi设置":"killall found-control-center"},{"关闭蓝牙设置":"killall blueman-manager"},{"关闭系统帮助":"killall evince"}, {"打开摄像头工具":"cheese"},{"关闭摄像头工具":"killall cheese"}]'
# app_list = json.loads(app_list)


class ShadowWindow(QWidget):
    def __init__(self):
        super().__init__()
        available_geometry = QApplication.desktop().availableGeometry()
        self.shadow_win_width = 480
        self.shadow_win_height = available_geometry.height()
        self.init_ui()
        self._is_drag = False  # 拖动
        self.move_DragPosition = QPoint()

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

    # 重写原有方法 Start
    def paintEvent(self, event):
        # 创建一个QPainter对象，并为当前窗口提供绘图功能
        painter = QPainter(self)
        pixmap = QPixmap('ui/icon/侧边栏背景.png').scaled(self.size())
        painter.drawPixmap(0, 0, pixmap)

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