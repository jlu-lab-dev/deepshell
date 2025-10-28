from PyQt5.QtWidgets import QWidget, QApplication, QVBoxLayout, QSpacerItem, QSizePolicy

from ui.chat.bubble_message import BubbleMessage
from ui.chat.chat_box import ChatScrollArea, ChatScrollBar
from public_types import PublicTypes


class MeetingWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(95)
        self.setMaximumHeight(922)

        self.desktop = QApplication.desktop()

        # 获取显示器分辨率大小
        self.screenRect = self.desktop.screenGeometry()
        self.height = self.screenRect.height()

        h = self.height - 280
        self.setFixedHeight(h)
        layout = QVBoxLayout()
        layout.setSpacing(0)
        self.adjustSize()
        self.setObjectName('meetingwidget');
        # 生成滚动区域
        self.scrollArea = ChatScrollArea(self.height)
        scrollBar = ChatScrollBar()
        self.scrollArea.setVerticalScrollBar(scrollBar)
        # self.scrollArea.setGeometry(QRect(9, 9, 261, 211))
        # 生成滚动区域的内容部署层部件
        self.scrollAreaWidgetContents = QWidget(self.scrollArea)
        self.scrollAreaWidgetContents.adjustSize()
        self.scrollAreaWidgetContents.setMinimumSize(50, 100)
        # 设置滚动区域的内容部署部件为前面生成的内容部署层部件
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.scrollArea.setFixedHeight(720)
        layout.addWidget(self.scrollArea)
        self.layout0 = QVBoxLayout()
        self.layout0.setSpacing(0)
        self.scrollAreaWidgetContents.setLayout(self.layout0)
        self.setLayout(layout)

        self.spacerItemAdded = False

        # 保持最新消息在当前光标处
        self.scrollArea.verticalScrollBar().rangeChanged.connect(
            lambda: self.scrollArea.verticalScrollBar().setValue(
                self.scrollArea.verticalScrollBar().maximum()
            )
        )

        self.scrollArea.setStyleSheet(
            '''
            QScrollArea {background-color: transparent;}
            '''
        )

        self.scrollArea.viewport().setStyleSheet(
            '''
            background-color: transparent;
            '''

        )


    def add_message_item(self, bubble_message, index=1):
        if index:
            self.layout0.addWidget(bubble_message)
        else:
            item_count = self.layout0.count()
            self.layout0.insertWidget(item_count-1, bubble_message)
        # self.set_scroll_bar_last()
        self.add_vertical_spacer()



    def add_vertical_spacer(self):
        if not self.spacerItemAdded:
            self.layout0.addItem(QSpacerItem(10, 100, QSizePolicy.Preferred, QSizePolicy.Expanding))
            self.spacerItemAdded = True

    def switchViewType(self, mode):
        if PublicTypes.viewType == "sidebar":
            h = self.height - 280
            self.setFixedHeight(h)
            self.scrollArea.setFixedHeight(h)
            self.setFixedWidth(480  - 36)
            self.scrollArea.setFixedWidth(480 - 36)
            self.scrollAreaWidgetContents.setFixedWidth(480 - 36)
            for i in range(self.layout0.count()):
                wid0 = self.layout0.itemAt(i).widget()
                if isinstance(wid0, BubbleMessage):
                    wid0.message.setStyleSheet(
                        '''
                        background-color: rgba(54,54,54,204);
                        border-radius:10px;
                        padding:10px;
                        color: white;
                        '''
                    )
        elif PublicTypes.viewType == "windows":
            self.setFixedHeight(560)
            self.scrollArea.setFixedHeight(560)
            self.setFixedWidth(1164)
            self.scrollArea.setFixedWidth(1164)
            self.scrollAreaWidgetContents.setFixedWidth(1164)
            for i in range(self.layout0.count()):
                wid0 = self.layout0.itemAt(i).widget()
                if isinstance(wid0,BubbleMessage):
                    wid0.message.setStyleSheet(
                        '''
                        background-color: rgba(204,204,204,204);
                        border-radius:10px;
                        padding:10px;
                        color: black;
                        '''
                    )
        else:
            raise NotImplementedError("illegal type")
