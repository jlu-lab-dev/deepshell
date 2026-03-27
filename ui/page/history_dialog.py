from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QLineEdit, QMessageBox, QDesktopWidget
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QPen, QIcon

from config.config_manager import ConfigManager


class HistoryDialog(QWidget):
    """历史对话模态对话框"""
    conversation_selected = pyqtSignal(str)  # 发出选中的 conversation_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(480, 520)
        self.setObjectName('history_dialog')
        self.setStyleSheet('''
            #history_dialog {
                border-radius: 15px;
            }
        ''')

        self.conversations = []  # 当前显示的会话列表（过滤后）
        self.all_conversations = []  # 全部会话

        self._init_ui()
        self._init_connections()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 标题栏
        top_bar = self._create_top_bar()
        layout.addWidget(top_bar)

        # 主内容
        content = self._create_content()
        layout.addWidget(content)

    def _create_top_bar(self):
        top_bar = _BoxTitle(self)
        top_bar_layout = QHBoxLayout()

        title_label = QLabel("历史记录")
        title_label.setStyleSheet("font-size: 16px; color: #E0E0E0;")

        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("QPushButton{background-color:transparent;border:none;}")
        close_btn.setIcon(QIcon('ui/icon/icon_关闭_窗口模式@2x.png'))
        close_btn.setIconSize(QSize(24, 24))
        close_btn.clicked.connect(self.close)

        top_bar_layout.addWidget(title_label)
        top_bar_layout.addStretch(1)
        top_bar_layout.addWidget(close_btn)
        top_bar.setLayout(top_bar_layout)
        return top_bar

    def _create_content(self):
        content_widget = _HistoryContent(self)
        self.scroll_area = content_widget.scroll_area
        self.search_input = content_widget.search_input
        self.list_container = content_widget.list_container
        self.empty_label = content_widget.empty_label
        return content_widget

    def _init_connections(self):
        self.search_input.textChanged.connect(self._on_search_changed)

    def load_conversations(self):
        """从数据库加载会话列表，每次打开时调用以刷新"""
        try:
            from database.repository.conversation_repository import ConversationRepository
            self.repo = ConversationRepository()
            self.all_conversations = self.repo.list_conversations(50)
            self.conversations = self.all_conversations
            self._render_list()
        except Exception as e:
            print(f"加载历史会话失败: {e}")
            self.all_conversations = []
            self.conversations = []
            self._render_list()

    def _render_list(self):
        """渲染会话列表"""
        # 清空列表容器
        while self.list_container.layout.count():
            item = self.list_container.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.conversations:
            self.empty_label.show()
            self.scroll_area.hide()
            return

        self.empty_label.hide()
        self.scroll_area.show()

        for conv in self.conversations:
            item = _ConversationItem(conv, self)
            item.open_clicked.connect(self._on_item_open)
            item.delete_clicked.connect(self._on_item_delete)
            self.list_container.layout.addWidget(item)

    def _on_search_changed(self, text: str):
        """搜索框文字变化时过滤列表"""
        if not text.strip():
            self.conversations = self.all_conversations
        else:
            self.conversations = [
                c for c in self.all_conversations
                if text.lower() in c.title.lower()
            ]
        self._render_list()

    def _on_item_open(self, conversation_id: str):
        """用户点击打开某条历史会话"""
        self.conversation_selected.emit(conversation_id)
        self.close()

    def _on_item_delete(self, conversation_id: str):
        """用户点击删除某条历史会话（无确认弹窗）"""
        try:
            self.repo.delete_conversation(conversation_id)
            # 从列表中移除并重新渲染
            self.all_conversations = [c for c in self.all_conversations if c.id != conversation_id]
            self.conversations = self.all_conversations
            # 如果搜索框有内容，需要过滤
            search_text = self.search_input.text()
            if search_text:
                self.conversations = [
                    c for c in self.all_conversations
                    if search_text.lower() in c.title.lower()
                ]
            self._render_list()
        except Exception as e:
            QMessageBox.warning(self, "删除失败", f"删除会话时出错：{e}")

    def move_to_center(self):
        desktop = QDesktopWidget()
        screen = desktop.screenGeometry()
        self.move(
            int((screen.width() - self.width()) / 2),
            int((screen.height() - self.height()) / 2)
        )

    # ── 拖拽窗口实现 ──
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = True
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if self.moving:
            self.move(event.globalPos() - self.offset)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.moving = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        painter.setPen(QColor(0, 0, 0, 10))
        painter.setBrush(QColor(45, 45, 48))  # 深色背景 #2D2D30
        painter.drawRoundedRect(self.rect(), 15, 15)


class _BoxTitle(QWidget):
    """对话框标题栏"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName('box_title')
        self.setStyleSheet('''
            #box_title {
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                background-color: #2D2D30;
            }
        ''')
        self.installEventFilter(self)
        self.setFixedHeight(48)


class _HistoryContent(QWidget):
    """历史对话框主内容区"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setObjectName('history_content')
        self.setStyleSheet('''
            #history_content {
                background-color: #2D2D30;
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 15px;
            }
        ''')
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(10)

        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索历史对话...")
        self.search_input.setFixedHeight(36)
        self.search_input.setStyleSheet('''
            QLineEdit {
                background-color: #3C3C3C;
                border: 1px solid #4A4A4A;
                border-radius: 8px;
                padding: 0 12px;
                color: #E0E0E0;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
            QLineEdit:focus {
                border: 1px solid #6B9EFF;
            }
        ''')
        # 搜索图标
        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # 滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet('''
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #3C3C3C;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: #6B6B6B;
                border-radius: 3px;
            }
        ''')

        # 列表容器
        self.list_container = _ConversationListContainer()
        self.scroll_area.setWidget(self.list_container)

        # 空状态提示
        self.empty_label = QLabel("暂无历史对话")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #888888; font-size: 14px; padding: 40px;")
        self.empty_label.hide()

        layout.addWidget(self.scroll_area)
        layout.addWidget(self.empty_label)


class _ConversationListContainer(QWidget):
    """会话列表容器"""
    def __init__(self):
        super().__init__()
        self.setObjectName('conv_list_container')
        self.setStyleSheet('#conv_list_container { background-color: transparent; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignTop)
        self.spacer = None
        self.layout = layout


class _ConversationItem(QWidget):
    """单条会话项"""
    open_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)

    def __init__(self, conversation, parent=None):
        super().__init__(parent)
        self.conversation = conversation
        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(70)
        self.setObjectName('conv_item')
        self.setStyleSheet('''
            #conv_item {
                background-color: #3C3C3C;
                border-radius: 10px;
            }
            #conv_item:hover {
                background-color: #4A4A4A;
            }
        ''')

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 左侧：图标 + 内容
        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        title_label = QLabel(self.conversation.title)
        title_label.setStyleSheet("color: #E0E0E0; font-size: 14px; font-weight: 500;")
        title_label.setMaximumWidth(320)
        title_label.setWordWrap(False)
        title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        meta_label = QLabel()
        created = self.conversation.created_at
        if created:
            date_str = created.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = ""
        meta_label.setText(f"{date_str}  ·  {self.conversation.function_type or ''}")
        meta_label.setStyleSheet("color: #888888; font-size: 12px;")

        left_layout.addWidget(title_label)
        left_layout.addWidget(meta_label)

        # 右侧：删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setFixedSize(48, 28)
        delete_btn.setStyleSheet('''
            QPushButton {
                background-color: transparent;
                color: #FF6B6B;
                border: 1px solid #FF6B6B;
                border-radius: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #FF6B6B;
                color: white;
            }
        ''')
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.conversation.id))

        layout.addLayout(left_layout, 1)
        layout.addWidget(delete_btn)

        # 点击整条记录打开会话
        self.setCursor(Qt.PointingHandCursor)
        self.mousePressEvent = lambda e: self.open_clicked.emit(self.conversation.id)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    dialog = HistoryDialog()
    dialog.load_conversations()
    dialog.show()
    sys.exit(app.exec_())
