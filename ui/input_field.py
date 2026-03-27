import os
import logging

from pathlib import Path
from urllib.parse import urlparse
from PyQt5.QtWidgets import QTextEdit, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QFileDialog, QApplication
from PyQt5.QtGui import QIcon, QPixmap, QDropEvent, QDragEnterEvent
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QThread, QTimer
from langchain_core.documents.base import Document

from chat.preprompt_task import PrePromptTask
from speech.voice_recognition import VoiceRecognition
from translation.select_botton import language_select_layout
from ai_audio.audio_tool import AudioProcessor
from ocr.ocr_text import TextProcessor
from ui.button.websearch_button import WebSearchButton
from ui.button.agent_mode_button import AgentModeButton
from ui.file_thumbnail import HorizontalThumbnailScrollArea
from utils.document_loader import DocumentProcessor
from ui.theme_manager import ThemeManager


class InputField(QFrame):
    capture_voice_signal = pyqtSignal()
    send_signal = pyqtSignal(str, str, list)
    websearch_signal = pyqtSignal(bool)
    agent_mode_signal = pyqtSignal(str)  # 'pipeline' or 'react'

    def __init__(self):
        super().__init__()
        self.theme_manager = ThemeManager()
        self.init_ui()
        self.is_zoomed = False
        self.capture_voice_flag = False
        self.voice_message = ""
        self.last_voice_message = ""
        self.parsing_file_list = []

        self.pre_prompt_task = PrePromptTask()
        self.pre_prompt_task.complete_signal.connect(self.ai_callback)
        self.pre_prompt_task.update_signal.connect(self.update_pre_prompt)
        
        # 连接主题切换信号
        self.theme_manager.theme_changed.connect(self.apply_theme)

    def init_ui(self):
        # 设置样式
        self.resize(410, 126)
        self.setAcceptDrops(True)  # 启用拖拽支持

        # 输入框
        self.input_text_edit = QTextEdit()
        self.input_text_edit.setPlaceholderText("有什么问题尽管问我")
        self.input_text_edit.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.input_text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input_text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.input_text_edit.installEventFilter(self)  # 安装事件过滤器
        self.input_text_edit.setAcceptDrops(False)

        # 放大/缩小按钮
        self.unfold_icon_path = "ui/icon/icon_输入框_展开.png"
        self.fold_icon_path = "ui/icon/icon_输入框_收起.png"
        self.zoom_button = QPushButton()
        self.zoom_button.setIcon(QIcon(self.unfold_icon_path))
        self.zoom_button.setIconSize(QSize(16, 16))
        self.zoom_button.setFixedSize(16, 16)
        self.zoom_button.clicked.connect(self.toggle_zoom)

        # 麦克风按钮
        microphone_icon_path = "ui/icon/icon_输入框_麦克风.png"
        self.microphone_button = QPushButton()
        self.microphone_button.setIcon(QIcon(microphone_icon_path))
        self.microphone_button.setIconSize(QSize(18, 24))
        self.microphone_button.setFixedSize(24, 24)
        self.microphone_button.clicked.connect(self.capture_voice)

        # 麦克风语音输入
        self.voiceInput = VoiceRecognition()
        self.voiceInput.VoiceRecognitionSignal.connect(self.receive_voice_message)
        self.timerInput = QTimer(self)
        self.timerInput.timeout.connect(self.listeningToWaitingInput)  # 输入栏“聆听中”到“等待中”的自动转换

        # 麦克风语音动画
        self.image_folder = 'ui/icon/audio_input_loading'
        self.image_files = sorted([os.path.join(self.image_folder, f) for f in os.listdir(self.image_folder) if
                                   f.endswith(('.png', '.jpg', '.jpeg'))])
        self.current_image_index = 0
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_mic_icon)

        # 联网搜索
        self.websearch_button = WebSearchButton()
        self.websearch_button.clicked_signal.connect(self.switch_websearch_enabled)

        # 文件上传按钮
        self.upload_file_button = QPushButton()
        upload_file_icon_path = "ui/icon/icon_输入框_附件.png"
        self.upload_file_button.setIcon(QIcon(upload_file_icon_path))
        self.upload_file_button.setIconSize(QSize(22, 24))
        self.upload_file_button.setFixedSize(24, 24)
        self.upload_file_button.clicked.connect(self.upload_file)

        # 发送按钮
        send_icon_path = "ui/icon/icon_输入框_发送.png"
        self.send_button = QPushButton()
        self.send_button.setIcon(QIcon(send_icon_path))
        self.send_button.setIconSize(QSize(24, 21))
        self.send_button.setFixedSize(24, 24)
        self.send_button.clicked.connect(self.send_message)

        # 输入框布局
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_text_edit)
        input_layout.addWidget(self.zoom_button, alignment=Qt.AlignTop)

        # Agent 模式切换按钮（仅 AI Agent 功能下显示）
        self.agent_mode_button = AgentModeButton()
        self.agent_mode_button.mode_changed.connect(self.agent_mode_signal)
        self.agent_mode_button.hide()

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.microphone_button)
        button_layout.addWidget(self.websearch_button)
        button_layout.addWidget(self.agent_mode_button)
        #文本翻译的layout
        self.language_layout=language_select_layout()
        button_layout.addLayout(self.language_layout)
        #文本翻译layout end
        button_layout.addStretch()
        button_layout.addWidget(self.upload_file_button)
        button_layout.addWidget(self.send_button)

        # 底部缩略图布局
        self.bottom_layout = QHBoxLayout()
        self.thumbnail_scroll_area = HorizontalThumbnailScrollArea(close_btn_visible=True)
        self.thumbnail_scroll_area.delete_signal.connect(self.delete_upload_file)

        # 整体布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(input_layout)
        main_layout.addLayout(button_layout)
        main_layout.addLayout(self.bottom_layout)
        self.setLayout(main_layout)

        self.upload_file_list = []  # 上传文件list
        self.doc_list = []   # 附件解析内容list
        
        # 在所有组件创建完成后应用主题
        self.apply_theme(self.theme_manager.get_current_theme())

    def apply_theme(self, theme_name):
        """应用主题样式"""
        colors = self.theme_manager.get_colors()
        
        # 设置输入框容器样式
        self.setStyleSheet(f"""
            QFrame {{
                background: {colors['input_bg']};
                border: 1px solid {colors['input_border']};
                border-radius: 12px;
            }}
        """)
        
        # 设置文本编辑框样式
        self.input_text_edit.setStyleSheet(f"""
            QTextEdit {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei";
                font-weight: 400;
                font-size: 14px;
                color: {colors['input_text']};
                line-height: 20px;
                background: transparent;
                border: none;
                padding: 4px;
            }}

            QTextEdit QScrollBar:vertical {{
                width: 8px;
                background: {colors['scrollbar_bg']};
                margin: 0px;
            }}

            QTextEdit QScrollBar::handle:vertical {{
                background: {colors['scrollbar_handle']};
                min-height: 30px;
                border-radius: 4px;
            }}
            
            QTextEdit QScrollBar::handle:vertical:hover {{
                background: {colors['scrollbar_handle_hover']};
            }}

            QTextEdit QScrollBar::add-line:vertical, 
            QTextEdit QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}

            QTextEdit QScrollBar:horizontal {{
                height: 0px;
            }}
        """)
        
        # 更新按钮样式 - Cursor风格
        button_style = f"""
            QPushButton {{
                background: {colors['button_bg']};
                border: 1px solid {colors['button_border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QPushButton:hover {{
                background: {colors['button_hover']};
                border: 1px solid {colors['button_border']};
            }}
            QPushButton:pressed {{
                background: {colors.get('button_pressed', colors['button_bg'])};
            }}
        """
        self.thumbnail_scroll_area.apply_theme(colors)
        self.zoom_button.setStyleSheet(button_style)
        self.microphone_button.setStyleSheet(button_style)
        self.upload_file_button.setStyleSheet(button_style)
        self.send_button.setStyleSheet(button_style)
    
    def toggle_zoom(self):
        if not self.is_zoomed:
            self.resize(410, 502)
            self.input_text_edit.setFixedHeight(436)
            self.zoom_button.setIcon(QIcon(self.fold_icon_path))
            self.is_zoomed = True
        else:
            self.resize(410, 126)
            self.input_text_edit.setFixedHeight(78)
            self.zoom_button.setIcon(QIcon(self.unfold_icon_path))
            self.is_zoomed = False

    # 处理语音输入事件
    def capture_voice(self):
        self.handle_capture_voice_input()

    def receive_voice_message(self, message):
        self.voice_message += message
        current_text = self.get_input_text()
        updated_text = current_text + message
        self.set_input_text(updated_text)

    def handle_capture_voice_input(self):
        print("handle_capture_voice-input")
        if self.capture_voice_flag:
            """停止录音时的处理"""
            self.animation_timer.stop()
            # 恢复原始图标（带过渡效果）
            self.microphone_button.setIcon(QIcon("ui/icon/icon_输入框_麦克风.png"))
            # 重置索引
            self.current_image_index = 0
            self.capture_voice_flag = False
            self.voiceInput.stop_recognition()
            self.timerInput.stop()
            self.voice_message = ""
        else:
            self.capture_voice_flag = True
            if self.image_files:
                self.current_image_index = 0
                self.animation_timer.start(50)  # 使用50ms间隔
            else:
                # 没有动画帧时使用默认图标
                self.microphone_button.setIcon(QIcon("ui/icon/icon_输入框_麦克风.png"))
            self.voiceInput.start()
            self.timerInput.start(30000)
            self.voice_message = ""

    def listeningToWaitingInput(self):  # 聆听中到等待中的自动转换函数
        if self.voice_message != self.last_voice_message:
            self.last_voice_message = self.voice_message
        else:
            self.capture_voice()

    def update_mic_icon(self):
        """动态更新麦克风图标"""
        if self.image_files:
            # 加载当前帧图片
            current_image = self.image_files[self.current_image_index]
            try:
                # 保持宽高比缩放
                pixmap = QPixmap(current_image).scaled(
                    18, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.microphone_button.setIcon(QIcon(pixmap))
                # 更新索引（带缓冲机制）
                self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
            except:
                logging.error(f"无法加载图片: {current_image}")

    def show_language_select_layout(self, layout):
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            widget.show()

    def hide_language_select_layout(self, layout):
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            widget.hide()

    def show_agent_mode_button(self):
        """Show the Pipeline/ReAct toggle (used when AI Agent function is active)."""
        self.agent_mode_button.show()

    def hide_agent_mode_button(self):
        """Hide the toggle (used for all other functions)."""
        self.agent_mode_button.hide()
        self.agent_mode_button.reset()

    def extract_file_path(self, url):
        """从 file:// URL 中提取文件路径并转换为标准路径"""
        parsed_url = urlparse(url)
        file_path = parsed_url.path
        if file_path.startswith('/'):
            file_path = file_path[1:]
        return file_path

    def upload_file(self, file_path=None):
        logging.info(file_path)

        if not file_path:
            options = QFileDialog.Options()
            file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*)", options=options)

        logging.info(file_path)
        if file_path not in self.upload_file_list:
            if self.is_supported_file_type(file_path):
                if len(self.upload_file_list) == 0:  # 如果是上传的第一个附件，则添加下方滚动区域
                    self.bottom_layout.addWidget(self.thumbnail_scroll_area)
                    self.thumbnail_scroll_area.show()
                self.upload_file_list.append(file_path)

                # 新建线程进行内容解析
                self.parse_thread = Parse2TextThread(file_path)
                self.parse_thread.finished_signal.connect(self.parse2text_finished)
                self.set_send_button_status(False)
                self.parsing_file_list.append(file_path)
                self.parse_thread.start()

                # 加载缩略图
                self.load_thumbnail()
            else:
                logging.info("Unsupported file type.")
        else:
            logging.info("File Already Uploaded.")

    def load_thumbnail(self):
        # 清空thumbnail_layout
        self.thumbnail_scroll_area.clear_thumbnail()

        # 从self.upload_file_list中加载缩略图
        for file_path in self.upload_file_list:
            self.thumbnail_scroll_area.add_thumbnail(file_path)

    def delete_upload_file(self, file_path):
        if file_path in self.upload_file_list:
            index = self.upload_file_list.index(file_path)
            self.upload_file_list.pop(index)
            if index < len(self.doc_list):
                self.doc_list.pop(index)

        # 检查是否还有缩略图
        if self.thumbnail_scroll_area.get_thumbnail_num() == 0:
            self.bottom_layout.removeWidget(self.thumbnail_scroll_area)  # 从底部布局中移除滚动区域
            self.thumbnail_scroll_area.hide()

        self.updateGeometry()

    # 预提示词 Start
    def ai_callback(self, text):
        display_text = text[:50] + "..." if len(text) > 50 else text  # 截断超过50个字符的文本
        self.input_text_edit.setText(display_text)

    def update_pre_prompt(self, text):
        display_text = text[:50] + "..." if len(text) > 50 else text
        self.input_text_edit.setText(display_text)

    def load_pre_prompt(self):
        self.pre_prompt_task.set_topic(self.get_reference())
        self.pre_prompt_task.start()
    # 预提示词 End

    def parse2text_finished(self, result, file_path):
        self.doc_list.append(result)
        for i in range(self.thumbnail_scroll_area.get_thumbnail_num()):
            thumbnail = self.thumbnail_scroll_area.get_ith_thumbnail(i)
            if thumbnail.file_path == file_path:
                thumbnail.set_close_btn_clickable(True)
                break

        # 加载预提示词
        if len(self.input_text_edit.toPlainText()) == 0:
            self.load_pre_prompt()
        self.set_send_button_status(True)

    def parse_doc(self, doc):  # 将doc解析为字符串列表
        flattened = []
        for item in doc:
            if isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, list):
                        flattened.extend(self.flatten_list(sub_item))
                    else:
                        flattened.append(sub_item)
            elif isinstance(item, Document):
                flattened.append(item.page_content)
            else:
                flattened.append(item)  # 添加字符串元素
        return flattened

    def get_reference(self):
        reference_list = []  # 存放参考资料的字符串列表
        for idx, doc in enumerate(self.doc_list):  # doc 可能是字符串、列表、Document实例
            reference_list.extend(self.parse_doc(doc))  # 将doc转成纯字符串加入到reference_list中

        references = ""
        for idx, reference in enumerate(reference_list):
            references += f"用户上传附件内容 {idx + 1}：" + reference + "\n"
        return references

    def send_message(self):
        user_input = self.input_text_edit.toPlainText()
        if len(user_input) == 0 or not self.send_button.isEnabled():
            return
        else:
            full_message = "用户输入：" + user_input + '\n'
            full_message += self.get_reference()

            self.send_button.setEnabled(False)
            self.send_signal.emit(user_input, full_message, self.thumbnail_scroll_area.get_thumbnail_list())

            self.init_status()

            self.thumbnail_scroll_area.clear_thumbnail()
            self.bottom_layout.removeWidget(self.thumbnail_scroll_area)  # 从底部布局中移除滚动区域
            self.thumbnail_scroll_area.hide()

            self.updateGeometry()

    def get_input_text(self):
        return self.input_text_edit.toPlainText()

    def set_input_text(self, text):
        self.input_text_edit.setText(text)

    def clear_input_text(self):
        self.input_text_edit.clear()

    def set_microphone_button_status(self, status):
        self.microphone_button.setEnabled(status)

    def switch_websearch_enabled(self, status):
        self.websearch_signal.emit(status)

    def set_send_button_status(self, status):
        self.send_button.setEnabled(status)

    def init_status(self):
        self.upload_file_list.clear()
        self.doc_list.clear()

        # 清空缩略图，并从底部布局中移除滚动区域
        self.thumbnail_scroll_area.clear_thumbnail()
        self.bottom_layout.removeWidget(self.thumbnail_scroll_area)
        self.thumbnail_scroll_area.hide()

        self.updateGeometry()

        if hasattr(self, "parse_thread"):
            if self.parse_thread.isRunning():
                self.parse_thread.stop()

        if self.pre_prompt_task.isRunning():
            self.pre_prompt_task.stop()

        self.clear_input_text()
        self.send_button.setEnabled(True)

    def is_supported_file_type(self, file_path):
        file_extension = Path(file_path).suffix.lower()
        return file_extension in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.txt', '.pdf', '.docx', '.md', '.csv', '.xlsx', '.mp3', '.m4a', '.flac','.wav']

    # 处理按下回车和粘贴的事件
    def eventFilter(self, obj, event):
        # 检查是否是你想要监听的对象和事件类型
        if obj == self.input_text_edit and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.send_message()
                return True  # 表示事件已被处理

            # 监听Ctrl+V
            if (event.modifiers() & Qt.ControlModifier) and (event.key() == Qt.Key_V):
                clipboard = QApplication.clipboard()  # 获取剪贴板
                clipboard_content = clipboard.text()

                if clipboard_content.startswith('file://'):
                    file_path = self.extract_file_path(clipboard_content)
                    self.upload_file(file_path)
                else:
                    cursor = self.input_text_edit.textCursor()
                    cursor.insertText(clipboard_content)
                    self.input_text_edit.setTextCursor(cursor)
                return True  # 表示事件已被处理

            return super().eventFilter(obj, event)

        # 调用父类的事件过滤器，保证其他事件正常处理
        return super().eventFilter(obj, event)

    # 拖拽触发时
    def dragEnterEvent(self, event: QDragEnterEvent):
        # 检查是否携带文件路径
        if event.mimeData().hasUrls():
            event.acceptProposedAction()  # 允许拖拽
        else:
            event.ignore()  # 忽略非文件拖拽

    # 拖拽释放时
    def dropEvent(self, event: QDropEvent):
        # 获取所有拖拽的文件路径
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                self.upload_file(file_path)
            event.acceptProposedAction()  # 确认事件处理完成
        else:
            event.ignore()


class Parse2TextThread(QThread):
    finished_signal = pyqtSignal(list, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        res_list = self.parse2text(self.file_path)
        self.finished_signal.emit(res_list, self.file_path)

    def parse2text(self, file_path):
        res_list = []
        file_extension = Path(file_path).suffix.lower()
        if file_extension in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']:
            T = TextProcessor()
            res = T.ui_use_ocr(file_path)
            res_list.append(res)
        elif file_extension in ['.txt', '.pdf', '.docx', '.md', '.csv', '.xlsx']:
            document_processor = DocumentProcessor(chunk_size=10, chunk_overlap=2)
            documents = document_processor.load_document(file_path)
            res_list.extend(documents)
        elif file_extension in ['.wav', '.mp3', '.m4a', '.flac']:
             audio_processor = AudioProcessor()
             res = audio_processor.whisper_audio_to_text(file_path)
             res_list.append(res)
        else:
            logging.info("Unsupported file type.")

        return res_list
    
    def stop(self):
        """停止线程"""
        self.quit()  # 调用 QThread 的 quit 方法
        self.wait()  # 等待线程结束
