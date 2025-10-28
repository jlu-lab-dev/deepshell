from pathlib import Path

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QHBoxLayout,
                             QPushButton, QFrame, QApplication, QWidget, QListWidget, QListWidgetItem, QFileDialog,
                             QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QIcon, QMouseEvent


class UploadDialog(QDialog):
    files_selected = pyqtSignal(list)  # 文件选择信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFixedSize(600, 400)
        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
                border-radius: 8px;
            }
        """)
        #存储选择的文件路径
        self.selected_files = []
        self.initUI()
        self.setAcceptDrops(True)


    def _handle_click_upload(self, event):
        """点击拖拽区域时打开文件对话框"""
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要上传的文件",
            "",  # 初始目录
            "支持的文件类型 (*.pdf *.docx *.txt *.md);;所有文件 (*)",  # 文件过滤器
            options=options
        )

        if files:
            self.selected_files.extend(files)
            self._update_file_list()  # 更新文件列表显示

    def _handle_confirmation(self):
        """统一确认处理"""
        if not self.selected_files:
            QMessageBox.warning(self, "提示", "请至少选择一个文件！")
            return

        # 最终确认时发送信号
        self.files_selected.emit(self.selected_files.copy())  # 发送副本
        super().accept()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ======== 自定义标题栏 ========
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background: #FFFFFF; border-radius: 8px 8px 0 0;")
        title_bar.mousePressEvent = self.mousePressEvent
        title_bar.mouseMoveEvent = self.mouseMoveEvent
        title_bar.mouseReleaseEvent = self.mouseReleaseEvent

        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 0, 12, 0)
        title_layout.setSpacing(0)

        # 标题文字
        title_label = QLabel("上传文件")
        title_label.setStyleSheet("""
            QLabel {
                font-family: Microsoft YaHei;
                font-size: 14px;
                color: #333333;
                border-left:none;
                border-right:none;
            }
        """)

        # 关闭按钮
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setIcon(QIcon("ui/icon/知识库/icon_知识库_关闭.png"))
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #F0F0F0;
            }
            QPushButton:pressed {
                background: #E0E0E0;
            }
        """)
        self.close_btn.clicked.connect(self.close)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.close_btn)

        main_layout.addWidget(title_bar)

        # ======== 主要内容区域 ========
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(40, 20, 40, 30)
        content_layout.setSpacing(20)

        #文件列表
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
                    QListWidget {
                        background: #FFFFFF;
                        border: 1px solid #E0E0E0;
                        border-radius: 4px;
                        padding: 4px;
                    }
                    QListWidget::item {
                        border-bottom: 1px solid #F0F0F0;
                    }
                    QListWidget::item:hover {
                        background: #F8F8F8;
                    }
                """)
        # 在内容布局中添加文件列表
        content_layout.insertWidget(1, self.file_list)
        self.file_list.hide()  # 初始隐藏

        # 拖拽区域
        self.drop_area = QFrame()
        self.drop_area.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 2px dashed #CCCCCC;
                border-radius: 8px;
            }
        """)
        self.drop_area.setFixedHeight(240)

        # 拖拽区域内容
        drop_layout = QVBoxLayout(self.drop_area)
        drop_layout.setAlignment(Qt.AlignCenter)

        icon = QLabel()
        icon.setPixmap(QIcon("ui/icon/知识库/icon_知识库_上传文件.png").pixmap(64, 64))
        text1 = QLabel("点击或拖拽文件或文件夹至此区域即可上传")
        text2 = QLabel("支持单次或批量上传")

        # 样式设置
        icon.setStyleSheet("border:none;")
        text1.setStyleSheet("""
            font-family: Microsoft YaHei;
            font-size: 16px;
            color: #666666;
            margin-top: 15px;
            border:none;
        """)
        text2.setStyleSheet("""
            font-family: Microsoft YaHei;
            font-size: 14px;
            color: #999999;
            margin-top: 8px;
            border:none;
        """)

        drop_layout.addWidget(icon, 0, Qt.AlignCenter)
        drop_layout.addWidget(text1)
        drop_layout.addWidget(text2, 0, Qt.AlignCenter)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.setStyleSheet("""
                    QPushButton {
                        background: #FFFFFF;
                        border: 1px solid #CCCCCC;
                        border-radius: 6px;
                        color: #666666;
                        font-family: Microsoft YaHei;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background: #F5F5F5;
                    }
                """)
        cancel_btn.clicked.connect(self.reject)
        # 确定按钮
        ok_btn = QPushButton("确定")
        ok_btn.setFixedSize(80, 36)
        ok_btn.setStyleSheet("""
                    QPushButton {
                        background: #007AFF;
                        border-radius: 6px;
                        color: #FFFFFF;
                        font-family: Microsoft YaHei;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background: #0066CC;
                    }
                    QPushButton:pressed {
                        background: #0052A3;
                    }
                """)
        ok_btn.clicked.connect(self._handle_confirmation)

        self.drop_area.mousePressEvent = self._handle_click_upload

        self.tips_label = QLabel("点击或拖拽文件或文件夹至此区域继续上传")
        self.tips_label.setStyleSheet("""
                    QLabel {
                        font-family: Microsoft YaHei;
                        font-size: 14px;
                        color: #999999;
                        margin-top: 8px;
                        border:none;
                    }
                """)
        self.tips_label.setAlignment(Qt.AlignCenter)
        self.tips_label.hide()

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)

        content_layout.addWidget(self.drop_area)
        content_layout.addWidget(self.tips_label)
        content_layout.addLayout(btn_layout)



        main_layout.addWidget(content_widget)

    def _update_file_list(self):
        """更新文件列表显示"""
        self.file_list.clear()
        # 设置列表整体样式
        self.file_list.setStyleSheet("""
            QListWidget {
                border: 1px dashed #007AFF;
                border-radius: 8px;
                background: #FFFFFF;
                padding: 4px;
            }
            QListWidget::item {
                border: none;
                background: transparent;
            }
            QListWidget::item:hover {
                background: #F8F8F8;
            }
        """)
        self.file_list.mousePressEvent = self._handle_click_upload

        for file_path in self.selected_files:
            # 创建自定义列表项
            item_widget = QWidget()
            item_widget.setStyleSheet("background: transparent;")
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(8, 4, 8, 4)

            # 文件类型图标
            icon_label = QLabel()
            file_type = Path(file_path).suffix.lower()
            icon_map = {
                ".pdf": "icon_知识库_pdf.png",
                ".doc": "icon_知识库_文件_word.png",
                ".docx": "icon_知识库_文件_word.png",
                ".txt": "icon_知识库_文件_txt.png",
                ".md": "icon_知识库_markdown.png",
            }
            icon_path = f"ui/icon/{icon_map.get(file_type, 'icon_知识库_文件_默认.png')}"
            icon_label.setPixmap(QIcon(icon_path).pixmap(24, 24))

            # 文件名标签
            file_label = QLabel(Path(file_path).name)
            file_label.setStyleSheet("""
                QLabel {
                    font-size: 14px; 
                    color: #333333;
                    background: transparent;
                    border: none;
                }
            """)

            # 删除按钮
            delete_btn = QPushButton()
            delete_btn.setFixedSize(24, 24)
            delete_btn.setIcon(QIcon("ui/icon/知识库/icon_知识库_关闭.png"))
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                }
                QPushButton:hover {
                    background: #F0F0F0;
                    border-radius: 12px;
                }
            """)
            delete_btn.clicked.connect(lambda _, p=file_path: self._remove_file(p))

            # 布局管理
            item_layout.addWidget(icon_label)
            item_layout.addWidget(file_label, 1)  # 添加伸缩因子
            item_layout.addWidget(delete_btn)

            # 创建列表项
            list_item = QListWidgetItem()
            list_item.setSizeHint(item_widget.sizeHint())
            list_item.setFlags(Qt.NoItemFlags)  # 禁用默认选择样式
            self.file_list.addItem(list_item)
            self.file_list.setItemWidget(list_item, item_widget)



        # 控制显示状态
        has_files = len(self.selected_files) > 0
        self.file_list.setVisible(has_files)
        self.tips_label.setVisible(has_files)  # 显示持续上传提示
        self.drop_area.setVisible(not has_files)

    def _remove_file(self, file_path):
        """移除单个文件"""
        if file_path in self.selected_files:
            self.selected_files.remove(file_path)
            self._update_file_list()



    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and event.y() < 40:
            self.dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.dragging = False

    # 拖拽事件处理
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_area.setStyleSheet("""
                QFrame {
                    background: #F0F9FF;
                    border: 2px dashed #007AFF;
                    border-radius: 8px;
                }
            """)

    def dragLeaveEvent(self, event):
        self.drop_area.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border: 2px dashed #CCCCCC;
                border-radius: 8px;
            }
        """)

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.selected_files.extend(files)  # 追加而不是替换
        self._update_file_list()
        self.drop_area.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border: 2px dashed #CCCCCC;
                border-radius: 8px;
            }
        """)

    def closeEvent(self, event):
        self.drop_area.setStyleSheet("""
            QFrame {
                background: #FAFAFA;
                border: 2px dashed #CCCCCC;
                border-radius: 8px;
            }
        """)
        super().closeEvent(event)

    def on_drop_area_clicked(self, event):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件",
            "",
            "Supported Files (*.pdf *.doc *.docx *.txt *.md);;All Files (*)"
        )
        if files:
            self.selected_files.extend(files)
            self._update_file_list()
            self.files_selected.emit(files)

    def get_selected_files(self):
        """获取最终选择的文件列表"""
        return self.selected_files

    def accept(self):
        """重写确认方法"""
        if not self.selected_files:
            QMessageBox.warning(self, "提示", "请至少选择一个文件！")
            return
        super().accept()


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)

    window = UploadDialog()
    window.show()

    app.exec_()