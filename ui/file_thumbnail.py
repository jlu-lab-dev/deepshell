import os
import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QSize, Qt, QFileInfo
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QLabel, QPushButton, QFileIconProvider, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, \
    QSizePolicy


class FileThumbnail(QLabel):
    delete_self_signal = pyqtSignal('qint64')  # 用于通知父类删除该实例

    def __init__(self, file_path, is_click_able=True, close_btn_clickable=False, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self._clickable = is_click_able
        self.close_btn_clickable = close_btn_clickable
        self.init_ui()

    def init_ui(self):
        # 关闭按钮
        self.close_button = QPushButton(self)
        self.close_button.setFixedSize(16, 16)
        self.close_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;  /* 可保留轻微圆角，保证hover效果 */
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.1);  /* 悬停时微微变亮 */
            }
        """)
        self.close_button.setIcon(QIcon('ui/icon/icon_附件_删除.png'))
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.clicked.connect(self.delete_self)
        self.close_button.setEnabled(self.close_btn_clickable)

        # 缩略图图片
        file_extension = Path(self.file_path).suffix.lower()
        if file_extension in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
            self.create_img_thumbnail()
        elif file_extension in ['.txt', '.pdf', '.doc', '.docx', '.md', '.csv', '.xlsx', '.mp3', '.m4a', '.flac', '.wav','.xmind','.ppt','.pptx']:
            self.create_doc_card()


    def create_img_thumbnail(self):
        self.setFixedSize(60, 60)
        self.setStyleSheet("""
                    background: #2b2b2b;
                    border: 1px solid #3c3c3c;
                    border-radius: 8px;
                """)

        # 图片则直接获取缩略图显示
        pixmap = QPixmap(self.file_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation).scaled(60, 60) # 确保充满方框
        self.setPixmap(pixmap)
        self.close_button.move(38, 6)  # 添加关闭按钮
        self.close_button.raise_()

    def create_doc_card(self):
        self.setFixedSize(144, 60)
        self.setStyleSheet("""
            background: #2b2b2b;
            border: 1px solid #3c3c3c;
            border-radius: 8px;
        """)

        # 文件需要创建卡片：缩略图+文件信息
        file_info = QFileInfo(self.file_path)
        icon_provider = QFileIconProvider()
        pixmap = QIcon(icon_provider.icon(file_info)).pixmap(64, 64).scaled(45, 48)
        thumbnail_label = QLabel()
        thumbnail_label.setFixedSize(45, 48)
        thumbnail_label.setPixmap(pixmap) # 缩略图

        # 文件信息及布局
        file_name = Path(self.file_path).name if len(Path(self.file_path).name) <= 4 else f"{Path(self.file_path).name[0:4]}..."
        file_name_label = QLabel(file_name)
        file_name_label.setFixedSize(67, 16)
        file_name_label.setStyleSheet("""
                                font-family: Microsoft YaHei;
                                font-weight: 400;
                                font-size: 14px;
                                color: #FFFFFF;
                                border: none;
                            """)
        size_text = f"{Path(self.file_path).suffix.upper().split('.')[1]}，{file_info.size() / 1024:.2f} KB"
        size_text = size_text if len(size_text) <= 9 else f"{size_text[0:7]}..."
        file_size_label = QLabel(size_text)
        file_size_label.setFixedSize(71, 14)
        file_size_label.setStyleSheet("""
                                font-family: Microsoft YaHei;
                                font-weight: 400;
                                font-size: 14px;
                                color: #B3B3B3;
                                border: none;
                            """)

        info_layout = QVBoxLayout()
        info_layout.addWidget(file_name_label)
        info_layout.addWidget(file_size_label)

        # 卡片布局
        layout = QHBoxLayout()
        layout.addSpacing(6)
        layout.setContentsMargins(6, 6, 15, 6)
        layout.addWidget(thumbnail_label)
        layout.addLayout(info_layout)
        self.setLayout(layout)
        self.close_button.move(122, 6)  # 添加关闭按钮
        self.close_button.raise_()

    def delete_self(self):
        self.delete_self_signal.emit(id(self))

    def set_close_btn_visible(self, status):
        self.close_button.setVisible(status)

    def set_self_clickable(self, status):
        self._clickable = status

    def set_close_btn_clickable(self, status):
        self.close_button.setEnabled(status)

    def mousePressEvent(self, event):
        if self._clickable and event.button() == Qt.LeftButton:
            """处理文件打开"""
            if sys.platform == 'win32':
                os.startfile(self.file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.file_path])
            else:
                subprocess.run(['xdg-open', self.file_path])
        super().mousePressEvent(event)


class HorizontalThumbnailScrollArea(QScrollArea):
    """只允许水平滚动的自定义滚动区域"""
    delete_signal = pyqtSignal(str)  # 通知父窗口删除移除该文件

    def __init__(self, thumbnail_list=None, close_btn_visible=False, thumbnail_clickable=True, parent=None):
        super().__init__(parent)
        self.close_btn_visible = close_btn_visible
        self.thumbnail_clickable = thumbnail_clickable

        self.theme_colors = {
            'bg': '#2b2b2b',  # 深色主题背景
            'border': '#3c3c3c',
            'scrollbar_bg': '#2b2b2b',
            'scrollbar_handle': '#555555'
        }
        self.init_ui()

        self.thumbnail_list = []
        if thumbnail_list is not None:
            for thumbnail in thumbnail_list:
                thumbnail.set_close_btn_visible(self.close_btn_visible)
                thumbnail.set_self_clickable(self.thumbnail_clickable)
                self.thumbnail_layout.addWidget(thumbnail)
            self.thumbnail_list = thumbnail_list

    def init_ui(self):
        self.setFixedHeight(72)
        self.setStyleSheet(f"""
            QScrollArea {{
                background: {self.theme_colors['bg']};
                border: 1px solid {self.theme_colors['border']};
                border-radius: 8px;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {self.theme_colors['scrollbar_bg']};
                height: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {self.theme_colors['scrollbar_handle']};
                min-width: 30px;
                border-radius: 3px;
            }}
        """)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet(f"background: {self.theme_colors['bg']};")
        self.scroll_content.setFixedHeight(72)
        self.thumbnail_layout = QHBoxLayout(self.scroll_content)
        self.thumbnail_layout.setSpacing(6)
        self.thumbnail_layout.setContentsMargins(6, 0, 6, 0)
        self.thumbnail_layout.setAlignment(Qt.AlignLeft)
        self.setWidget(self.scroll_content)

    def apply_theme(self, colors):
        """允许外部主题同步"""
        self.theme_colors = colors
        self.setStyleSheet(f"""
            QScrollArea {{
                background: {colors['input_bg']};
                border: 1px solid {colors['input_border']};
                border-radius: 8px;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: {colors['scrollbar_bg']};
                height: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {colors['scrollbar_handle']};
                min-width: 30px;
                border-radius: 3px;
            }}
        """)
        self.scroll_content.setStyleSheet(f"background: {colors['input_bg']};")

    def add_thumbnail(self, file_path):
        thumbnail = FileThumbnail(file_path)
        thumbnail.set_close_btn_visible(self.close_btn_visible)
        thumbnail.delete_self_signal.connect(self.delete_thumbnail)
        thumbnail.set_self_clickable(self.thumbnail_clickable)
        self.thumbnail_layout.addWidget(thumbnail, 0, Qt.AlignVCenter)
        self.thumbnail_list.append(thumbnail)

    def delete_thumbnail(self, thumbnail_id):
        for idx in range(self.thumbnail_layout.count()):
            thumbnail = self.thumbnail_layout.itemAt(idx).widget()
            if id(thumbnail) == thumbnail_id:
                file_path = thumbnail.file_path  # 先获取文件路径以便后续从列表中删除

                self.thumbnail_layout.removeWidget(thumbnail)  # 从布局中移除并删除缩略图
                self.thumbnail_list.remove(thumbnail)
                thumbnail.deleteLater()
                self.delete_signal.emit(file_path)
                break

    def clear_thumbnail(self):
        for i in reversed(range(self.thumbnail_layout.count())):
            widget = self.thumbnail_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        self.thumbnail_list.clear()

    def get_thumbnail_num(self):
        return len(self.thumbnail_list)

    def get_thumbnail_list(self):
        return self.thumbnail_list

    def get_ith_thumbnail(self, ith):
        return self.thumbnail_list[ith]

    def wheelEvent(self, event):
        # 将垂直滚轮事件转换为水平滚动
        if event.angleDelta().y() != 0:
            scroll_bar = self.horizontalScrollBar()
            scroll_bar.setValue(
                scroll_bar.value() - event.angleDelta().y()
            )
        event.accept()

    def set_close_btn_visible(self, status):
        self.close_btn_visible = status

    def set_thumbnail_clickable(self, status):
        self.thumbnail_clickable = status