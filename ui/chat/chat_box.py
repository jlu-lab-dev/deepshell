from PyQt5.QtCore import pyqtSignal, Qt, QEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSpacerItem, QSizePolicy, QScrollBar, QScrollArea

from ui.chat.bubble_message import BubbleMessage


class ChatScrollBar(QScrollBar):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            '''
          QScrollBar:vertical {
              border-width: 0px;
              border: none;
              width:0px;
              min-width: 0px;  // 新增最小宽度限制
              max-width: 0px;  // 新增最大宽度限
              background: transparent;
          }
          QScrollBar::handle:vertical {
              width: 0px;
              background: transparent;
              border: none;  // 新增边框清除

          }
          QScrollBar::add-line:vertical {
          }
          QScrollBar::sub-line:vertical {
              border: none;
              background: none;
              width: 0px;
              height: 0px;
          }
          QScrollBar::sub-page:vertical {
          }

          QScrollBar::add-page:vertical {
              width:0px;
              background: none;
          }
            '''
        )


class ChatScrollArea(QScrollArea):
    def __init__(self, height, parent=None):
        super().__init__(parent)
        self.area_height = height
        self.user_interacted = False  # 用户是否主动交互过滚动条
        self.auto_scroll_enabled = True  # 是否允许自动滚动
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(self.area_height)
        self.setStyleSheet('''
            QScrollArea { background-color: transparent; border: none; }
        ''')
        self.viewport().setStyleSheet('background-color: transparent;')

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 使用自定义滚动条
        scrollBar = ChatScrollBar()
        self.setVerticalScrollBar(scrollBar)

        # 事件监听
        self.verticalScrollBar().installEventFilter(self)
        self.verticalScrollBar().valueChanged.connect(self.handle_scroll_position)
        self.verticalScrollBar().rangeChanged.connect(self.handle_new_content)

    def eventFilter(self, obj, event):
        # 检测用户交互（滚轮/拖动）
        if obj == self.verticalScrollBar() and event.type() == QEvent.Wheel:
            self.user_interacted = True
            self.auto_scroll_enabled = (self.verticalScrollBar().value() == self.verticalScrollBar().maximum())
        return super().eventFilter(obj, event)

    def handle_scroll_position(self, value):
        # 用户滚动到底部时恢复自动滚动
        if value == self.verticalScrollBar().maximum():
            self.auto_scroll_enabled = True

    def handle_new_content(self):
        # 新内容到来时的处理
        if self.auto_scroll_enabled:
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().maximum()
            )

    def reset_auto_scroll(self):
        """外部可手动重置为自动滚动模式"""
        self.auto_scroll_enabled = True
        self.user_interacted = False


class ChatBox(QWidget):
    delete_index_history = pyqtSignal(str)

    def __init__(self, width, height):
        super().__init__()
        self.box_width = width
        self.box_height = height
        self.init_ui()
        self.spacerItemAdded = False

    def init_ui(self):
        self.resize(self.box_width, self.box_height)
        self.setMaximumHeight(self.box_height)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setObjectName('chat_widget')

        # 生成滚动区域
        self.scrollArea = ChatScrollArea(self.box_height)
        # 生成滚动区域的内容部署层部件
        self.scrollAreaContents = QWidget()
        self.scrollAreaContents.setMinimumSize(50, 100)
        self.scrollAreaContents.adjustSize()
        self.msg_layout = QVBoxLayout()
        self.msg_layout.setSpacing(0)
        self.scrollAreaContents.setLayout(self.msg_layout)
        # 设置滚动区域的内容部署部件为前面生成的内容部署层部件
        self.scrollArea.setWidget(self.scrollAreaContents)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(self.scrollArea)
        self.setLayout(layout)
        self.adjustSize()

    def add_message_item(self, bubble_message, index=1):
        if index:
            bubble_message.delete_signal.connect(self.remove_message_item)
            self.msg_layout.addWidget(bubble_message)
        else:
            item_count = self.msg_layout.count()
            self.msg_layout.insertWidget(item_count-1, bubble_message)
        self.add_vertical_spacer()
        self.scrollArea.handle_new_content()

    def add_vertical_spacer(self):
        if not self.spacerItemAdded:
            self.msg_layout.addItem(QSpacerItem(10, 100, QSizePolicy.Preferred, QSizePolicy.Expanding))
            self.spacerItemAdded = True

    def remove_message_item(self, bubble_message):
        self.delete_index_history.emit(bubble_message.message.text())
        self.msg_layout.removeWidget(bubble_message)
        bubble_message.hide()

    def set_scroll_bar_value(self, val):
        self.scrollArea.verticalScrollBar().setValue(val)

    def switchViewType(self):
        self.setFixedHeight(self.box_height)
        self.scrollArea.setFixedHeight(self.box_height)
        for i in range(self.msg_layout.count()):
            wid0 = self.msg_layout.itemAt(i).widget()
            if isinstance(wid0,BubbleMessage):
                wid0.updatePlayIcon()
                if i==0 or i%2==1:
                    wid0.message.setStyleSheet(
                        '''
                        background-color: rgba(54,54,54,204);
                        border-radius:10px;
                        padding:10px;
                        color: white;
                        '''
                    )
                else:
                    wid0.message.setStyleSheet(
                        '''
                        background-color: rgba(0,93,255,204);
                        border-radius:10px;
                        padding:10px;
                        color: white;
                        '''
                    )
        self.setMaximumWidth(432)
        self.setFixedWidth(432)
        self.scrollAreaContents.setFixedWidth(432)
        self.scrollArea.setFixedWidth(432)
        self.update()

    def update(self) -> None:
        super().update()
        self.scrollAreaContents.adjustSize()
        self.scrollArea.update()

    def clearLayout(self):
        while self.msg_layout.count():
            item = self.msg_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.spacerItemAdded = False
        self.scrollArea.user_scrolled = False  # 清空内容时重置用户滚动标志
        self.add_vertical_spacer()

    def switch_init(self, function_name):
        #清空内容
        self.clearLayout()