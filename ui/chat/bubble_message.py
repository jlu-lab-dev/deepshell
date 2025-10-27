import re
import markdown

from enum import Enum
from PIL import Image
from PyQt5 import QtGui
from PyQt5.QtWidgets import QLabel, QSizePolicy, QWidget, QPushButton, QHBoxLayout, QSpacerItem, QVBoxLayout, \
    QApplication
from PyQt5.QtCore import pyqtSignal, Qt, QThread, QSize, QTimer
from PyQt5.QtGui import QFont, QFontMetrics, QPixmap, QIcon, QMovie
from bs4 import BeautifulSoup

from ui.file_thumbnail import FileThumbnail
from ui.theme_manager import ThemeManager


# 返回消息的类型
class MessageType(Enum):
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"
    PAINT = "paint"
    WAITING = "waiting"
    LOADING = "loading"


class TextMessage(QLabel):
    def __init__(self, text, user_send=False, parent=None):
        super(TextMessage, self).__init__(text, parent)
        self.msg_text = text
        self.user_send = user_send
        self.theme_manager = ThemeManager()
        self.init_ui()
        self.theme_manager.theme_changed.connect(self.apply_theme)

    def init_ui(self):
        self.setMaximumWidth(450)
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setFont(QFont('微软雅黑', 12))
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.original_markdown_text = self.msg_text
        html_text = markdown.markdown(self.msg_text)
        self.setText(html_text)
        self.setAlignment(Qt.AlignLeft)
        
        self.apply_theme()

        self.font_metrics = QFontMetrics(QFont('微软雅黑', 12))
        if self.user_send:
            rect = self.font_metrics.boundingRect(self.msg_text)
        else:
            rect = self.font_metrics.boundingRect(html_text)
        self.setMaximumWidth(rect.width() + 30)

    def meeting_content_adjust_size(self):
        self.setMaximumWidth(500)
        self.adjustSize()

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        super(TextMessage, self).paintEvent(a0)

    def apply_theme(self, theme_name=None):
        """应用主题"""
        colors = self.theme_manager.get_colors()
        if self.user_send:
            self.setStyleSheet(f'''
                background-color: {colors['user_message_bg']};
                border-radius:12px;
                padding:10px;
                color: {colors['message_text']};
            ''')
        else:
            self.setStyleSheet(f'''
                background-color: {colors['ai_message_bg']};
                border-radius:12px;
                padding-left:0px;
                color: {colors['message_text']};
            ''')
    
    def update_text(self, text):
        self.original_markdown_text = text
        html_text = markdown.markdown(text)
        self.setText(html_text)
        rect = self.font_metrics.boundingRect(html_text)
        self.setMaximumWidth(rect.width() + 30)


class OpenImageThread(QThread):
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path

    def run(self) -> None:
        image = Image.open(self.image_path)
        image.show()


class ImageMessage(QLabel):
    def __init__(self, avatar, parent=None):
        super().__init__(parent)
        self.avatar = avatar
        self.init_ui()

    def init_ui(self):
        if isinstance(self.avatar, str):
            self.setPixmap(QPixmap(self.avatar))
            self.image_path = self.avatar
        elif isinstance(self.avatar, QPixmap):
            self.setPixmap(self.avatar)

        self.setMaximumWidth(420)
        self.setMaximumHeight(420)
        self.setScaledContents(True)
        
    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:  # 左键按下
            self.open_image_thread = OpenImageThread(self.image_path)
            self.open_image_thread.start()


class TableMessage(QLabel):
    def __init__(self, text, user_send=False, parent=None):
        super(TableMessage, self).__init__(parent)
        self.msg_text = text
        self.user_send = user_send
        self.theme_manager = ThemeManager()
        self.init_ui()
        self.theme_manager.theme_changed.connect(self.apply_theme)

    def init_ui(self):
        self.setWordWrap(True)
        self.setTextFormat(Qt.RichText)
        self.setFont(QFont('微软雅黑', 12))
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)  # 修改为Preferred

        # 解析内容并设置初始文本
        self.update_text(markdown.markdown(self.msg_text))
        
        # 设置对齐方式
        self.setAlignment(Qt.AlignLeft)
        
        # 应用主题样式
        self.apply_theme()

    def parse_table_data(self, text):
        """生成紧凑型HTML表格"""
        pattern = r"table>>(.*?)<<table"
        match = re.search(pattern, text, re.DOTALL)
        if match is None:
            return text

        csv_data = text[7:-7].strip()
        rows = [row.split(",") for row in csv_data.split("\n") if row.strip()]

        if not rows:
            return "无表格数据"

        # 紧凑型表格样式
        html = '''
        <table style="
            border-collapse: collapse;
            color: white;
            margin: 0;
            padding: 0;
            border: 1px solid rgba(255,255,255,0.3);
        ">
        '''
        for i, row in enumerate(rows):
            html += "<tr>"
            for cell in row:
                tag = "th" if i == 0 else "td"
                html += f'''
                <{tag} style="
                    padding: 2px 5px;
                    border: 1px solid rgba(255,255,255,0.2);
                ">
                    {cell.strip()}
                </{tag}>
                '''
            html += "</tr>"
        html += "</table>"
        return html

    def update_text(self, text):
        self.msg_text = text
        is_table = text.startswith("table>>") and text.endswith("<<table")

        if is_table:
            display_text = self.parse_table_data(text)
            self.setText(display_text)
            # 对表格内容使用固定宽度计算
            self.setMaximumWidth(350)  # 为表格设置合理最大宽度
        else:
            self.setText(markdown.markdown(text))
            # 对普通文本使用动态宽度计算
            fm = QFontMetrics(self.font())
            text_width = fm.horizontalAdvance(text) + 20
            self.setMaximumWidth(min(text_width, 350))  # 限制最大宽度

        self.adjustSize()  # 关键：让QLabel根据内容调整尺寸

    def apply_theme(self, theme_name=None):
        """应用主题"""
        colors = self.theme_manager.get_colors()
        if self.user_send:
            self.setStyleSheet(f'''
                background-color: {colors['user_message_bg']};
                border-radius:12px;
                padding:10px;
                color: {colors['message_text']};
            ''')
        else:
            self.setStyleSheet(f'''
                background-color: {colors['ai_message_bg']};
                border-radius:12px;
                padding-left:0px;
                color: {colors['message_text']};
            ''')
    
    def sizeHint(self):
        """覆盖默认尺寸计算"""
        hint = super().sizeHint()
        if self.msg_text.startswith("table>>"):
            return QSize(300, hint.height())  # 为表格固定宽度
        return QSize(min(hint.width(), 500), hint.height())


# 加载动画
class WaitingMessage(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(95, 36))
        self.setStyleSheet(
            '''
            background-color: #3f3f46;
            border-radius:10px;
            padding:10px;
            color: #e2e8f0;
            '''
        )

        self.current_image_index = 0
        self.total_images = 39  # 动画图片总数（0~39）
        self.timer = QTimer(self)  # 定义定时器
        self.timer.timeout.connect(self.updateLoadingImage)  # 定时器信号连接到updateImage方法
        self.timer.start(60)

    def updateLoadingImage(self):
        if self.current_image_index > self.total_images:
            self.current_image_index = 0  # 重置索引

        image_path = f"ui/icon/dialog_loading/{self.current_image_index:05d}.png"
        pixmap = QPixmap(image_path)

        if not pixmap.isNull():
            self.setPixmap(pixmap)
            self.current_image_index += 1
        else:
            print(f"图片加载失败: {image_path}")
            self.current_image_index += 1


class GifLoadingMessage(QWidget):
    def __init__(self, gif_path, text="", width=24, height=24, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        # GIF动画
        self.gif_label = QLabel(self)
        self.movie = QMovie(gif_path)
        self.movie.setScaledSize(QSize(width, height))
        self.gif_label.setMovie(self.movie)
        self.gif_label.setFixedSize(QSize(width, height))
        self.movie.start()
        # 文字
        self.text_label = QLabel(text, self)
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.text_label.setFont(QFont('微软雅黑', 12))
        self.text_label.setStyleSheet(
                '''
                background-color: transparent;
                border-radius:10px;
                padding-left:0px;
                color: #e2e8f0;
                '''
            )
        # 布局
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.gif_label)
        layout.addWidget(self.text_label)
        layout.setAlignment(Qt.AlignVCenter)
        self.setLayout(layout)


class BubbleMessage(QWidget):
    speech_signal = pyqtSignal(bool, str, QWidget)
    delete_signal = pyqtSignal(QWidget)

    def __init__(self, message, avatar, msg_type, font_size, user_send=False, parent=None, need_button=True, thumbnail_list=None):
        super().__init__(parent)
        self.message = message
        self.msg_type = msg_type
        self.avatar = avatar
        self.font_size = font_size
        self.user_send = user_send
        self.need_button = need_button
        self.thumbnail_list = thumbnail_list
        self.theme_manager = ThemeManager()

        self.isPlayAudio = False

        self.init_ui()
        
        # 连接主题切换信号
        self.theme_manager.theme_changed.connect(self.on_theme_changed)

    def init_ui(self):
        self.setStyleSheet(
            '''
                background: transparent;
                border-radius: 8px;
            '''
        )

        # 按钮样式 - Cursor风格
        self.button_style_template = """
            QPushButton {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 2px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {pressed};
            }}
        """
        
        # 播放按钮
        self.play_button = QPushButton(self)
        self.play_button.setFixedSize(QSize(20, 20))
        self.play_button.setIcon(QIcon('ui/icon/icon_播放_侧边栏模式@2x.png'))
        self.play_button.setIconSize(QSize(14, 14))
        self.play_button.clicked.connect(self.playAudio)
        self.play_button.setFlat(True)
        self.play_button.setEnabled(False)
        self.play_button.hide()

        # 拷贝按钮
        self.copy_button = QPushButton(self)
        self.copy_button.setFixedSize(QSize(20, 20))
        self.copy_button.setIcon(QIcon('ui/icon/icon_对话_拷贝.png'))
        self.copy_button.setIconSize(QSize(14, 14))
        self.copy_button.clicked.connect(self.copy_text)
        self.copy_button.setFlat(True)
        self.copy_button.setEnabled(False)
        self.copy_button.hide()

        # markdown按钮
        self.markdown_button = QPushButton(self)
        self.markdown_button.setFixedSize(QSize(20, 20))
        self.markdown_button.setIcon(QIcon('ui/icon/icon_对话_markdown.png'))
        self.markdown_button.setIconSize(QSize(14, 14))
        self.markdown_button.clicked.connect(self.copy_markdown)
        self.markdown_button.setEnabled(False)
        self.markdown_button.setFlat(True)
        self.markdown_button.hide()

        # 删除按钮
        self.delete_button = QPushButton(self)
        self.delete_button.setFixedSize(QSize(20, 20))
        self.delete_button.clicked.connect(self.delete_message)
        self.delete_button.setIcon(QIcon('ui/icon/icon_对话_删除.png'))
        self.delete_button.setIconSize(QSize(14, 14))
        self.delete_button.setEnabled(False)
        self.delete_button.setFlat(True)
        self.delete_button.hide()
        
        # 应用按钮主题
        self.apply_button_theme()

        # 根据消息类型创建消息
        self.message = self.generate_msg(self.message, self.msg_type, self.user_send)

        # 气泡布局
        message_layout = QHBoxLayout()
        message_layout.setSpacing(8)
        message_layout.setContentsMargins(0, 5, 5, 5)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(16)
        button_layout.setContentsMargins(0, 0, 0, 0)

        if self.user_send:  # 如果是用户发送的消息，则添加space将气泡推到右边
            message_layout.addItem(QSpacerItem(45 + 6, 35, QSizePolicy.Expanding, QSizePolicy.Minimum))
            message_layout.addWidget(self.message, 1)
        else:             # 如果是ai回复，则不添加space，直接在左边生成气泡
            message_layout.addWidget(self.message, 1)
            # 如果是AI回复的消息，则显示播放按钮
            if (self.msg_type == MessageType.TEXT or self.msg_type == MessageType.TABLE) and self.need_button:
                self.play_button.show()
                button_layout.addWidget(self.play_button, 0, Qt.AlignLeft)
                self.copy_button.show()
                button_layout.addWidget(self.copy_button, 0, Qt.AlignLeft)
                self.markdown_button.show()
                button_layout.addWidget(self.markdown_button, 0, Qt.AlignLeft)
                self.delete_button.show()
                button_layout.addWidget(self.delete_button, 0, Qt.AlignLeft)
                button_layout.addStretch(1)
            
            if self.need_button:
                message_layout.addItem(QSpacerItem(45 + 6, 35, QSizePolicy.Expanding, QSizePolicy.Minimum))
            else:
                message_layout.addItem(QSpacerItem(45 + 6, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(message_layout)
        if self.need_button:
            main_layout.addSpacing(4)
            main_layout.addLayout(button_layout)
        self.setLayout(main_layout)

    def generate_msg(self, message, msg_type, user_send):
        if msg_type == MessageType.TEXT:
            message = TextMessage(message, user_send)
        elif msg_type == MessageType.IMAGE:
            message = ImageMessage(message)
        elif msg_type == MessageType.TABLE:
            message = TableMessage(message, user_send)
        elif msg_type == MessageType.WAITING:
            message = WaitingMessage()
        elif msg_type == MessageType.LOADING:
            message = GifLoadingMessage(message.split('|')[0], message.split('|')[1])
        else:
            raise ValueError("未知的消息类型")
        return message

    def add_thumbnail_item(self, file_path):
        if self.thumbnail_layout.count() == 0:
            self.thumbnail_layout.addWidget(self.thumbnail_scroll_area)
        self.thumbnail_scroll_area.add_thumbnail(file_path)

    def playAudio(self):
        print("play audio:", self.message.text())
        if self.isPlayAudio:
            self.play_button.setIcon(QIcon('ui/icon/icon_播放_侧边栏模式@2x.png'))
        else:
            self.play_button.setIcon(QIcon('ui/icon/stop.png'))
        self.isPlayAudio = not self.isPlayAudio
        self.speech_signal.emit(self.isPlayAudio, self.message.text(), self)

    def playComplete(self):
        print("playComplete")
        self.play_button.setIcon(QIcon('ui/icon/icon_播放_侧边栏模式@2x.png'))
        self.isPlayAudio = False

    def updatePlayIcon(self):
        # 更新 play_button 图标
        if not self.isPlayAudio:
            self.play_button.setIcon(QIcon('ui/icon/icon_播放_侧边栏模式@2x.png'))
        else:
            self.play_button.setIcon(QIcon('ui/icon/stop.png'))

    def copy_text(self):
        QApplication.clipboard().setText(BeautifulSoup(self.message.text(), "html.parser").get_text())
        # 切换图标两秒后恢复
        self.copy_button.setIcon(QIcon('ui/icon/icon_对话_markdown_拷贝完成'))
        QTimer.singleShot(2000, lambda: self.copy_button.setIcon(QIcon('ui/icon/icon_对话_拷贝.png')))

    def copy_markdown(self):
        QApplication.clipboard().setText(self.message.original_markdown_text)
        # 切换图标两秒后恢复
        self.markdown_button.setIcon(QIcon('ui/icon/icon_对话_markdown_拷贝完成'))
        QTimer.singleShot(2000, lambda: self.markdown_button.setIcon(QIcon('ui/icon/icon_对话_markdown.png')))

    def delete_message(self):
        self.delete_signal.emit(self)

    def on_theme_changed(self, theme_name):
        """主题切换回调"""
        self.apply_button_theme()
    
    def apply_button_theme(self):
        """应用按钮主题"""
        colors = self.theme_manager.get_colors()
        button_style = self.button_style_template.format(
            bg=colors['button_bg'],
            border=colors['button_border'],
            hover=colors['button_hover'],
            pressed=colors.get('button_pressed', colors['button_bg'])
        )
        self.play_button.setStyleSheet(button_style)
        self.copy_button.setStyleSheet(button_style)
        self.markdown_button.setStyleSheet(button_style)
        self.delete_button.setStyleSheet(button_style)
    
    def update_button_status(self, status):
        self.copy_button.setEnabled(status)
        self.play_button.setEnabled(status)
        self.delete_button.setEnabled(status)
        self.markdown_button.setEnabled(status)


class ThumbnailMessage(QWidget):
    delete_signal = pyqtSignal(QWidget)
    def __init__(self,  user_send=False,  parent=None, thumbnail=None, file_path=None, close_btn_visible=False, thumbnail_clickable=True):
        super().__init__(parent)
        self.close_btn_visible = close_btn_visible
        self.thumbnail_clickable = thumbnail_clickable
        self.user_send = user_send
        
        
        if thumbnail is not None:
            self.thumbnail = thumbnail
        if file_path is not None:
            self.thumbnail = self.get_thumbnail_item_from_path(file_path)
        self.init_ui()
    def init_ui(self):
        self.setStyleSheet(
            '''
                background: transparent;
                border-radius: 8px;
            '''
        )
        
        self.thumbnail_layout = QHBoxLayout()
        self.thumbnail_layout.setSpacing(8)
        self.thumbnail_layout.setContentsMargins(0, 5, 5, 5)
        self.thumbnail.set_close_btn_visible(self.close_btn_visible)
        if self.user_send:  
            self.thumbnail_layout.addItem(QSpacerItem(45 + 6, 45, QSizePolicy.Expanding, QSizePolicy.Minimum))
            self.thumbnail_layout.addWidget(self.thumbnail)
        else:
            self.thumbnail_layout.addWidget(self.thumbnail)
            self.thumbnail_layout.addItem(QSpacerItem(45 + 6, 45, QSizePolicy.Expanding, QSizePolicy.Minimum))
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(self.thumbnail_layout)
        self.setLayout(main_layout)
        
    def get_thumbnail_item_from_path(self, file_path):
        thumbnail = FileThumbnail(file_path)
        thumbnail.set_close_btn_visible(self.close_btn_visible)
        thumbnail.set_self_clickable(self.thumbnail_clickable)
        return thumbnail


class ButtonMessage(QWidget):
    delete_signal = pyqtSignal(QWidget)
    def __init__(self,  func, user_send=False,  parent=None):
        super().__init__(parent)
        self.user_send = user_send
        self.button = QPushButton(func,self)
        # 设置圆角、边框及背景色样式
        self.button.setStyleSheet("""
            QPushButton {
                background-color: #2d3748;
                color: #e2e8f0;
                font-size: 14px;
                padding: 8px 16px;
                border: 1px solid #4a5568;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #374151;
                border-color: #6b7280;
            }
            QPushButton:pressed {
                background-color: #1f2937;
            }
        """)
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet(
            '''
                background: transparent;
                border-radius: 7px;
            '''
        )

        self.button_layout = QHBoxLayout()
        self.button_layout.setSpacing(8)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        if self.user_send:  
            self.button_layout.addItem(QSpacerItem(45 + 6, 45, QSizePolicy.Expanding, QSizePolicy.Minimum))
            self.button_layout.addWidget(self.button)
        else:
            self.button_layout.addWidget(self.button)
            self.button_layout.addItem(QSpacerItem(45 + 6, 45, QSizePolicy.Expanding, QSizePolicy.Minimum))
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(self.button_layout)
        self.setLayout(main_layout)

    def set_text(self, content):
        self.button.setText(content)

    def set_clickable(self, clickable):
        self.button.setEnabled(clickable)

