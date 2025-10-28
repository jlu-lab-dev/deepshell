# chat_box.py

from PyQt5.QtCore import pyqtSignal, Qt, QEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSpacerItem, QSizePolicy, QScrollBar, QScrollArea

from ui.chat.bubble_message import BubbleMessage
from ui.theme_manager import ThemeManager
from ui.utils import ViewMode


class ChatScrollBar(QScrollBar):
    def __init__(self):
        super().__init__()
        self.theme_manager = ThemeManager()
        self.apply_theme()
        self.theme_manager.theme_changed.connect(self.apply_theme)

    def apply_theme(self, theme_name=None):
        colors = self.theme_manager.get_colors()
        self.setStyleSheet(f'''
          QScrollBar:vertical {{
              border: none;
              width: 8px;
              background: {colors['scrollbar_bg']};
              margin: 0px;
          }}
          QScrollBar::handle:vertical {{
              background: {colors['scrollbar_handle']};
              min-height: 30px;
              border-radius: 4px;
          }}
          QScrollBar::handle:vertical:hover {{
              background: {colors['scrollbar_handle_hover']};
          }}
          QScrollBar::add-line:vertical,
          QScrollBar::sub-line:vertical {{
              border: none;
              background: none;
              height: 0px;
          }}
          QScrollBar::add-page:vertical,
          QScrollBar::sub-page:vertical {{
              background: none;
          }}
        ''')


class ChatScrollArea(QScrollArea):
    def __init__(self, height, parent=None):
        super().__init__(parent)
        self.area_height = height
        self.user_interacted = False
        self.auto_scroll_enabled = True
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(self.area_height)
        self.setStyleSheet('''
            QScrollArea { background-color: transparent; border: none; }
        ''')
        self.viewport().setStyleSheet('background-color: transparent;')

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        scrollBar = ChatScrollBar()
        self.setVerticalScrollBar(scrollBar)

        self.verticalScrollBar().installEventFilter(self)
        self.verticalScrollBar().valueChanged.connect(self.handle_scroll_position)
        self.verticalScrollBar().rangeChanged.connect(self.handle_new_content)

    def eventFilter(self, obj, event):
        if obj == self.verticalScrollBar() and event.type() == QEvent.Wheel:
            self.user_interacted = True
            self.auto_scroll_enabled = (self.verticalScrollBar().value() == self.verticalScrollBar().maximum())
        return super().eventFilter(obj, event)

    def handle_scroll_position(self, value):
        if value == self.verticalScrollBar().maximum():
            self.auto_scroll_enabled = True

    def handle_new_content(self):
        if self.auto_scroll_enabled:
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().maximum()
            )

    def reset_auto_scroll(self):
        self.auto_scroll_enabled = True
        self.user_interacted = False


class ChatBox(QWidget):
    delete_index_history = pyqtSignal(str)

    def __init__(self, width, height):
        super().__init__()
        self.box_width = width
        self.box_height = height
        self.theme_manager = ThemeManager()
        self.init_ui()
        self.spacerItemAdded = False

        self.theme_manager.theme_changed.connect(self.on_theme_changed)

    def init_ui(self):
        self.resize(self.box_width, self.box_height)
        self.setMaximumHeight(self.box_height)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setObjectName('chat_widget')

        self.scrollArea = ChatScrollArea(self.box_height)
        self.scrollAreaContents = QWidget()
        self.scrollAreaContents.setMinimumSize(50, 100)
        self.scrollAreaContents.adjustSize()
        self.msg_layout = QVBoxLayout()
        self.msg_layout.setSpacing(0)
        self.scrollAreaContents.setLayout(self.msg_layout)
        self.scrollArea.setWidget(self.scrollAreaContents)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.addWidget(self.scrollArea)
        self.setLayout(layout)
        self.adjustSize()

    def add_message_item(self, bubble_message, index=1):
        if index:
            if hasattr(bubble_message, 'delete_signal'):
                bubble_message.delete_signal.connect(self.remove_message_item)
            self.msg_layout.addWidget(bubble_message)
        else:
            item_count = self.msg_layout.count()
            self.msg_layout.insertWidget(item_count - 1, bubble_message)
        self.add_vertical_spacer()
        self.scrollArea.handle_new_content()

    def add_vertical_spacer(self):
        if not self.spacerItemAdded:
            self.msg_layout.addItem(QSpacerItem(10, 100, QSizePolicy.Preferred, QSizePolicy.Expanding))
            self.spacerItemAdded = True

    def remove_message_item(self, bubble_message):
        self.msg_layout.removeWidget(bubble_message)
        bubble_message.hide()

    def set_scroll_bar_value(self, val):
        self.scrollArea.verticalScrollBar().setValue(val)

    def on_theme_changed(self, theme_name):
        self.update_messages_theme()

    def update_messages_theme(self):
        colors = self.theme_manager.get_colors()
        for i in range(self.msg_layout.count()):
            wid0 = self.msg_layout.itemAt(i).widget()
            if isinstance(wid0, BubbleMessage):
                # NOTE: The logic for alternating colors seems to be based on index parity.
                # If AI and user messages are not strictly alternating, this might need revision.
                # Assuming AI is odd index, user is even.
                is_ai_message = (i % 2 == 1) or (i == 0)  # As per original logic
                bg_color = colors['ai_message_bg'] if is_ai_message else colors['user_message_bg']

                wid0.message.setStyleSheet(f'''
                    background-color: {bg_color};
                    border-radius:12px;
                    padding:10px;
                    color: {colors['message_text']};
                ''')

    # MODIFIED: The entire function is replaced to handle different view modes.
    def switchViewType(self, mode: ViewMode):
        """
        Switches the view type between sidebar and windowed mode.
        """
        if mode == ViewMode.SIDEBAR:
            # Set fixed size for sidebar mode
            self.setFixedHeight(self.box_height)
            self.setFixedWidth(self.box_width)
            self.scrollArea.setFixedHeight(self.box_height)
            self.scrollArea.setFixedWidth(self.box_width)

        elif mode == ViewMode.WINDOW:
            # Remove fixed size constraints for window mode, allowing it to expand
            # A large number is used for max size to effectively un-constrain it
            QSS_MAX_SIZE = 16777215
            self.setMaximumHeight(QSS_MAX_SIZE)
            self.setMaximumWidth(QSS_MAX_SIZE)
            # Set a reasonable minimum size for the chat box in window mode
            self.setMinimumSize(300, 200)

            # Also un-constrain the scroll area
            self.scrollArea.setMaximumHeight(QSS_MAX_SIZE)
            self.scrollArea.setMaximumWidth(QSS_MAX_SIZE)
            self.scrollArea.setMinimumSize(300, 200)

        # These actions are common to both mode switches
        self.update_messages_theme()
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
        self.scrollArea.reset_auto_scroll()
        self.add_vertical_spacer()

    def switch_init(self, function_name):
        self.clearLayout()