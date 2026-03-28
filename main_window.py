# main_window.py

import logging
import re
import datetime
import PyQt5.sip as sip

from PyQt5.QtCore import Qt, QTimer, QThread, QMetaObject, Q_ARG, pyqtSignal
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout, QSpacerItem, QSizePolicy, QMenu, QLabel

from ai_audio.audio_task import AudioTask
from ai_table.gen_report import generate_analyst_report
from ai_table.gen_table import generate_table
from ai_table.intro_ui import TableIntroPage
from ai_table.table_task import TableTask
from audio_transcription.intro_ui import AudioTranscriptionIntroPage
from ocr.intro_ui import OcrIntroPage
from ocr.ocr_task import OcrTask
from meeting.intro_ui import MeetingIntroPage
from meeting.meeting_box import MeetingWidget
from meeting.meeting_btn_widget import MeetingBottomWidget
from meeting.meeting_task import MeetingTask, MeetingFile
from mind_map.intro_ui import MindMapIntroPage
from mind_map.map_task import MapTask
from ppt.intro_ui import PPTIntroPage
from ppt.workflow.ppt_task import PPTTask
from ppt.makePPTByTemplate.mdtojson import PPTGenerator
from sys_agent.intro_ui import SysFuncIntro
from sys_agent.react_agent import ReActAgentController
from translation.intro_ui import TranslateIntroPage
from translation.translate_task import TranslateTask
from translation.translate_detect import TranslateDetect
from chat.chat_task import ChatTask
from chat.intro_page import ChatIntroPage
from speech.voice_recognition import VoiceRecognition
from speech.speech_task import Speech, SpeechTask
from ui.utils import AssistantMode, ViewMode
from utils.intro_ui import DocAnalysisIntroPage
from utils.open_local_app_task import OpenLocalAppTask
from draw.drawing_task import AiDrawingTask
from server_check import ServerCheck
from ui.button.knowledge_base_select_button import KnowledgeBaseSelectButton
from ui.button.model_select_button import ModelSelectButton
from ui.chat.bubble_message import BubbleMessage, MessageType, ThumbnailMessage, ButtonMessage, \
    WorkflowContainerMessage, AgentHistoryWidget
from ui.chat.chat_box import ChatBox
from ui.page.speech_page import SpeechPage
from ui.button.function_menu_button import FunctionMenuButton
from ui.input_field import InputField
from ui.knowledge_base.knowledge_base_home import KnowledgeBaseHome
from ui.button.new_dialog_button import NewDialogButton
from config.config_manager import ConfigManager
from chat.message_helpers import (
    is_json_message, parse_message_content, get_text_content,
    make_text_message, make_agent_workflow_message,
)


logging.basicConfig(level=logging.INFO)


class MainWin(QWidget):

    title_change_requested = pyqtSignal(str)

    def __init__(self, main_win_width, main_win_height):
        super().__init__()
        self.main_win_width = main_win_width
        self.main_win_height = main_win_height
        self.init_ui()
        self.func_init()

    def init_ui(self):
        self.setObjectName('mainwindow')
        self.setStyleSheet(
            '''
            #mainwindow{
                border-top-left-radius: 15px;
                border-top-right-radius: 15px;
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 15px;
            }
            '''
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)  # 背景透明
        self.resize(self.main_win_width, self.main_win_height)

        # 中间内容栈 Start
        self.contentStackWgt = QStackedWidget()

        self.chat_intro = ChatIntroPage()  # 智能问答，即主界面

        self.ppt_intro = PPTIntroPage()    # AI PPT

        self.translate_intro = TranslateIntroPage()  # 语种翻译

        self.ocr_intro = OcrIntroPage()    # OCR

        self.doc_analysis_intro = DocAnalysisIntroPage()  # 文档分析

        self.knowledge_base_home = KnowledgeBaseHome()    # 知识库

        self.table_intro = TableIntroPage()       # AI 表格

        self.meeting_intro = MeetingIntroPage()   # 会议记录

        self.mind_map_intro = MindMapIntroPage()  # 思维导图

        self.audio_transcription_intro = AudioTranscriptionIntroPage()  # 思维导图

        self.chat_box = ChatBox(410, self.main_win_height - 250)  # 聊天框
        self.chat_box.delete_index_history.connect(self.delete_index_history)
        self.chat_box.add_vertical_spacer()
        self.chat_box.hide()

        self.speech_page = SpeechPage()  # speech
        self.speech_page.collect_voice_signal.connect(self.handle_capture_voice)
        self.speech_page.stop_speech_signal.connect(self.stop_speech_signal_exchange)
        self.speech_page.hide()

        self.meetingWgt = MeetingWidget()  # 会议
        self.meetingWgt.hide()

        self.sys_func_intro = SysFuncIntro()

        self.contentStackWgt.addWidget(self.chat_intro)
        self.contentStackWgt.addWidget(self.ppt_intro)
        self.contentStackWgt.addWidget(self.translate_intro)
        self.contentStackWgt.addWidget(self.ocr_intro)
        self.contentStackWgt.addWidget(self.doc_analysis_intro)
        self.contentStackWgt.addWidget(self.table_intro)
        self.contentStackWgt.addWidget(self.meeting_intro)
        self.contentStackWgt.addWidget(self.mind_map_intro)
        self.contentStackWgt.addWidget(self.audio_transcription_intro)
        self.contentStackWgt.addWidget(self.chat_box)
        self.contentStackWgt.addWidget(self.speech_page)
        self.contentStackWgt.addWidget(self.meetingWgt)
        self.contentStackWgt.addWidget(self.sys_func_intro)
        self.contentStackWgt.setCurrentIndex(0)  # 设置初始页面
        # 中间内容栈 End

        # 功能按钮 Start
        self.new_dialog_btn = NewDialogButton()         # 新建对话按钮
        self.new_dialog_btn.clicked_signal.connect(self.new_dialog_handle)

        self.knowledge_base_select_btn = KnowledgeBaseSelectButton()
        self.knowledge_base_select_btn.selection_changed.connect(self.update_selected_kb)

        self.model_select_btn = ModelSelectButton()
        self.model_select_btn.model_switch.connect(self.switch_model)

        self.function_menu_btn = FunctionMenuButton()   # 新建菜单按钮
        self.function_menu_btn.function_selected.connect(self.handle_function_selection)

        hor_layout = QHBoxLayout()
        hor_layout.setSpacing(8)  # 设置按钮间距
        hor_layout.addWidget(self.new_dialog_btn)
        hor_layout.addWidget(self.knowledge_base_select_btn)
        hor_layout.addWidget(self.model_select_btn)
        hor_layout.addWidget(self.function_menu_btn)
        # 功能按钮 End

        # 底部按钮栈 Start
        self.bottomStackWgt = QStackedWidget()

        self.input_field = InputField()
        self.input_field.hide()
        self.input_field.send_signal.connect(self.handle_send_message)
        self.input_field.websearch_signal.connect(self.set_websearch_enabled)

        self.meeting_bottom_ui = MeetingBottomWidget()
        self.meeting_bottom_ui.hide()
        self.meeting_bottom_ui.switch_signal.connect(self.meeting_signal_handle)

        self.bottomStackWgt.addWidget(self.input_field)
        self.bottomStackWgt.addWidget(self.meeting_bottom_ui)
        self.bottomStackWgt.setCurrentIndex(0)
        # 底部按钮栈 End

        # 窗口整体布局
        layout = QVBoxLayout()
        layout.setContentsMargins(18, 0, 18, 12)
        layout.addWidget(self.contentStackWgt)
        layout.addItem(QSpacerItem(10, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        layout.addLayout(hor_layout)  # 加入水平布局
        layout.addWidget(self.bottomStackWgt)
        self.setLayout(layout)

        # 功能组件映射
        self.page_mapping = {
            "智能问答": {
                "main": self.chat_intro,
                "chat": self.chat_box,
                "bottom": self.input_field
            },
            "AI PPT": {
                "main": self.ppt_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            },
            "语种翻译": {
                "main": self.translate_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            },
            "AI 识图": {
                "main": self.ocr_intro,
                "chat": self.chat_box,
                "bottom": self.input_field
            },
            # "文档分析": {
            #     "main": self.doc_analysis_intro,
            #     "chat": self.chat_box,
            #     "bottom": self.input_field,
            # },
            "知识库": {
                "main": self.knowledge_base_home
            },
            "AI 表格": {
                "main": self.table_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            },
            "会议记录": {
                "main": self.meeting_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            },
            "思维导图": {
                "main": self.mind_map_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            },
            # "音频转写": {
            #     "main": self.audio_transcription_intro,
            #     "chat": self.chat_box,
            #     "bottom": self.input_field,
            # },
            "语音聊天": {
                "main": self.speech_page
            },
            "AI Agent": {
                "main": self.sys_func_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            },
        }

        # mode setting
        self.mode = AssistantMode.CHAT
        self.current_model = "DeepSeek-V3"
        self.current_input = None    # string
        self.current_bubble_message = None
        self.current_func = "智能问答"

        # knowledge base setting
        self.selected_kb_id_list = []

        # system function setting

    def func_init(self):
        self.serverCheck = ServerCheck()
        self.serverCheck.internet_change_signal.connect(self.internet_change_handle)
        self.serverCheck.start()

        self.waitingMessage = BubbleMessage('', '', MessageType.WAITING, 12, user_send=False)
        self.waitingMeetingMessage = BubbleMessage('', '', MessageType.WAITING, 12, user_send=False)

        self.sendTask = ChatTask()
        self.sendTask.complete_signal.connect(self.ai_callback)
        self.sendTask.update_signal.connect(self.update_ai_message)

        self.localAppTask = OpenLocalAppTask()

        self.speechTask = SpeechTask()
        self.speechTask.set_callback(self.speechTaskCallback)

        self.voiceInput = VoiceRecognition()
        self.voiceInput.VoiceRecognitionSignal.connect(self.receive_voice_message)
        # self.voiceInput.VoiceRecognitionSignal.connect(self.handle_send_voice_message)

        self.voice_message = ""
        self.last_voice_message = ""

        self.aiDrawingTask = AiDrawingTask()
        self.aiDrawingTask.complete_signal.connect(self.complete_drawing_handle)

        self.meetingTask = MeetingTask()
        self.meetingTask.message_ready_signal.connect(self.meeting_message_ready_handle)
        self.meetingTask.meeting_status_signal.connect(self.meeting_service_status_handle)

        self.timer = QTimer(self)  # 定义定时器
        self.timer.timeout.connect(self.start_meeting)  # 定时器信号连接到updateImage方法

        self.timerSend = QTimer(self)
        self.timerSend.timeout.connect(self.listeningToWaiting)  # "聆听中"到"等待中"的自动转换

        # Agent Controller Setup (ReAct only)
        self.agent_thread = QThread()
        self.agent_controller = ReActAgentController(self.current_model)
        self.agent_controller.moveToThread(self.agent_thread)

        # A dictionary to hold references to workflow step widgets
        self.workflow_step_widgets = {}
        self.current_workflow_container = None

        # Agent 工作流步骤数据收集（用于持久化到数据库）
        self._agent_steps = []
        self._react_thought_chain = []  # ReAct 推理链收集器

        # Connect AgentController signals
        # For simple chats (fallback) — ReAct doesn't have normal_update_signal,
        # but we still wire it through the same handlers for consistency
        self.agent_controller.workflow_step_started.connect(self.handle_workflow_step_started)
        self.agent_controller.workflow_step_finished.connect(self.handle_workflow_step_finished)
        self.agent_controller.finished_signal.connect(self.handle_agent_finished)
        self.agent_controller.error_signal.connect(self.handle_agent_error)

        self.agent_thread.start()

    def handle_function_selection(self, function_name):
        """集中处理功能切换时的UI"""
        self.sendTask.stop_flag = True
        self.agent_thread.quit()

        # 切换功能前保存当前对话
        self._save_current_conversation()

        config = self.page_mapping.get(function_name)
        if function_name != "知识库":
            self.title_change_requested.emit(function_name)
            # self.parent().change_title_midlabel(function_name)
        self.current_func = function_name

        self.model_select_btn.set_current_model("DeepSeek-V3")
        if config:
            if function_name == "知识库":
                main_widget = config["main"]
                main_widget.show()
            elif function_name == "语音聊天":
                main_widget = config["main"]
                main_widget.show()
                if self.contentStackWgt.indexOf(main_widget) == -1:
                    self.contentStackWgt.addWidget(main_widget)
                self.contentStackWgt.setCurrentWidget(main_widget)
            else:
                # 主显示区域操作
                main_widget = config["main"]
                main_widget.show()
                if self.contentStackWgt.indexOf(main_widget) == -1:
                    self.contentStackWgt.addWidget(main_widget)
                self.contentStackWgt.setCurrentWidget(main_widget)

                chat_widget = config["chat"]  # 获取chat组件
                if chat_widget:  # 如果存在chat组件
                    if self.contentStackWgt.indexOf(chat_widget) == -1:  # 检查是否已添加
                        self.contentStackWgt.addWidget(chat_widget)

                # 底部输入区域操作
                bottom_widget = config["bottom"]
                bottom_widget.show()
                self.new_dialog_btn.show()
                self.knowledge_base_select_btn.show()
                self.model_select_btn.show()
                self.function_menu_btn.show()
                bottom_widget.init_status()

                if function_name == '语种翻译':
                    bottom_widget.show_language_select_layout(bottom_widget.language_layout)
                else:
                    bottom_widget.hide_language_select_layout(bottom_widget.language_layout)

                if self.bottomStackWgt.indexOf(bottom_widget) == -1:  # 假设存在底部堆栈布局
                    self.bottomStackWgt.addWidget(bottom_widget)
                self.bottomStackWgt.setCurrentWidget(bottom_widget)

                # 统一的初始化接口
                if hasattr(main_widget, "switch_init"):
                    main_widget.switch_init(function_name)
                if hasattr(chat_widget, "switch_init"):
                    chat_widget.switch_init(function_name)
                if hasattr(bottom_widget, "switch_init"):
                    bottom_widget.switch_init(function_name)

                # Show/hide ReAct mode indicator button
                if function_name == "AI Agent":
                    self.input_field.show_agent_mode_button()
                else:
                    self.input_field.hide_agent_mode_button()

                self.function_menu_btn.show()
                self.new_dialog_btn.show()

                self.switch_init(function_name)
                print(f"成功切换到：{function_name}（主组件+底部输入）")
        else:
            print(f"未定义的功能：{function_name}")

    def switch_init(self, function_name):
        if self.sendTask.isRunning():
            self.sendTask.stop()
            self.show_waiting_message(False)
            self.current_bubble_message = None
            self.input_field.set_send_button_status(True)

        match function_name:
            case "智能问答":
                self.mode = AssistantMode.CHAT
                self.sendTask = ChatTask()
            case "AI PPT":
                self.mode = AssistantMode.CHAT
                self.sendTask = PPTTask()
                self.pgen = PPTGenerator()
                self.pgen.pptgen_complete_signal.connect(self.handle_gen_ppt)
            case "AI 表格":
                self.mode = AssistantMode.CHAT
                self.sendTask = TableTask()
            case "AI 识图":
                self.mode = AssistantMode.CHAT
                self.sendTask = OcrTask()
            case "会议记录":
                self.mode = AssistantMode.CHAT
                self.sendTask = AudioTask()
            case "语种翻译":
                self.mode = AssistantMode.CHAT
                self.sendTask = TranslateTask()
            case "思维导图":
                self.mode = AssistantMode.CHAT
                self.sendTask = MapTask()
            # case "音频转写":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = TranscriptionTask()
            # case "文档分析":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = DocumentTask()
            case _:  # 【增加一个默认case】
                if not hasattr(self, 'sendTask') or not isinstance(self.sendTask, ChatTask):
                    self.sendTask = ChatTask()
        self.sendTask.assistant.set_selected_kb(self.selected_kb_id_list)
        self.sendTask.complete_signal.connect(self.ai_callback)
        self.sendTask.update_signal.connect(self.update_ai_message)

    def show_waiting_message(self, show):  # 总是和BubbleMessage成对出现，send为True则显示，否则隐藏，待优化
        if show:
            if sip.isdeleted(self.waitingMessage):
                self.waitingMessage = BubbleMessage('', '', MessageType.WAITING, 12, user_send=False)
            self.chat_box.add_message_item(self.waitingMessage)
            self.waitingMessage.show()
        else:
            self.chat_box.remove_message_item(self.waitingMessage)
            self.waitingMessage.hide()
        self.input_field.set_send_button_status(False)

    # Send Start
    def update_ai_message(self, result):
        """更新AI消息内容，实现流式效果"""
        self.input_field.set_send_button_status(False)
        # 如果等待消息还在显示，先隐藏它
        if self.waitingMessage.isVisible():
            self.show_waiting_message(False)

        # 检查是否已经创建了BubbleMessage
        if not hasattr(self, 'current_bubble_message') or self.current_bubble_message is None:
            # 创建新的BubbleMessage
            if self.current_func == "AI 表格":
                self.current_bubble_message = BubbleMessage(result, '', msg_type=MessageType.TABLE, font_size=12, user_send=False)
            elif self.current_func == "AI 绘画":
                self.current_bubble_message = BubbleMessage(result, '', msg_type=MessageType.IMAGE, font_size=12, user_send=False)
            elif self.current_func == "AI Agent":
                self.current_bubble_message = BubbleMessage(result, '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
            else:
                self.current_bubble_message = BubbleMessage(result, '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
            self.speech_page.updateStatus('应答中')
            self.current_bubble_message.speech_signal.connect(self.handle_speech)
            self.chat_box.add_message_item(self.current_bubble_message)

        else:
            # 更新现有BubbleMessage的内容
            self.current_bubble_message.message.update_text(result)

    def ai_callback(self, result):
        """处理AI响应完成信号"""
        # 确保等待消息已隐藏
        self.show_waiting_message(False)

        bubble_message = None
        # 如果已经有BubbleMessage，更新它
        if hasattr(self, 'current_bubble_message') and self.current_bubble_message is not None:
            # 更新最终内容
            self.current_bubble_message.message.update_text(result)
            # BubbleMessage功能按钮启用
            self.current_bubble_message.update_button_status(True)
            bubble_message = self.current_bubble_message
        else:
            # 如果没有BubbleMessage，创建一个新的BubbleMessage
            if self.current_func == "AI 表格":
                bubble_message = BubbleMessage(result, '', msg_type=MessageType.TABLE, font_size=12, user_send=False)
            elif self.current_func == "AI 绘画":
                bubble_message = BubbleMessage(result, '', msg_type=MessageType.IMAGE, font_size=12, user_send=False)
            elif self.current_func == "AI Agent":
                self.current_bubble_message = BubbleMessage(result, '', msg_type=MessageType.TEXT, font_size=12, need_button=False, user_send=False)
            else:
                bubble_message = BubbleMessage(result, '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
            self.speech_page.updateStatus('应答中')
            bubble_message.speech_signal.connect(self.handle_speech)
            self.chat_box.add_message_item(bubble_message)
            bubble_message.update_button_status(True)

        if self.current_func == "AI 表格":
            pattern = r"table>>(.*?)<<table"
            match = re.search(pattern, result, re.DOTALL)
            if match:
                content = match.group(1).strip()
                table_path = generate_table(content)
                thumbnail_message = ThumbnailMessage(user_send=False, file_path=table_path)
                self.chat_box.scrollArea.reset_auto_scroll()
                self.chat_box.add_message_item(thumbnail_message)
            else:
                report_path = generate_analyst_report(result.strip())
                thumbnail_message = ThumbnailMessage(user_send=False, file_path=report_path)
                self.chat_box.scrollArea.reset_auto_scroll()
                self.chat_box.add_message_item(thumbnail_message)

        if self.current_func == "思维导图":
                base_name="思维导图"
                mindmap = self.sendTask.mind_map.parse_outline(text=result)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                file_name = f"{base_name}_{timestamp}.xmind"
                full_path = self.sendTask.mind_map.build_xmind(mindmap,file_name)
                if full_path is not None:
                    thumbnail_message = ThumbnailMessage(user_send=False,file_path =full_path)
                    print(full_path)
                    self.chat_box.scrollArea.reset_auto_scroll()
                    self.chat_box.add_message_item(thumbnail_message)

        if self.current_func == "AI PPT":
                base_name="AI PPT"
                bubble_message = ButtonMessage("生成PPT", user_send=False)
                self.chat_box.scrollArea.reset_auto_scroll()
                self.chat_box.add_message_item(bubble_message)
                bubble_message.button.clicked.connect(lambda: self.pgen.markdown_to_json(result))

        # 重置当前BubbleMessage引用
        self.current_bubble_message = None
        # 启用发送按钮
        self.input_field.set_send_button_status(True)

    def handle_workflow_step_started(self, step_id: str, text: str):
        """Handles the start of a workflow step."""
        self.show_waiting_message(False)

        # 如果当前没有容器，说明这是工作流的第一步
        if self.current_workflow_container is None:
            # 创建一个新的容器并添加到聊天框
            self.current_workflow_container = WorkflowContainerMessage()
            self.chat_box.add_message_item(self.current_workflow_container)

        # 在当前容器中添加一个新的步骤
        step_widget = self.current_workflow_container.add_step(text)

        # 存储这个步骤的引用，以便后续更新
        self.workflow_step_widgets[step_id] = step_widget

        # 收集步骤数据（用于持久化）
        self._agent_steps.append({
            'step_id': step_id,
            'text': text,
            'success': False,
            'message': text
        })

    def handle_workflow_step_finished(self, step_id: str, success: bool, message: str):
        """Finds an existing step widget and updates it to its 'finished' state."""
        step_widget = self.workflow_step_widgets.get(step_id)
        if step_widget:
            step_widget.set_finished(success, message)
        else:
            # Fallback in case the 'start' signal was missed
            print(f"Warning: Could not find a widget for step_id '{step_id}' to update.")
            final_message = f"[{'SUCCESS' if success else 'FAIL'}] {message}"
            # You could add a simple text bubble here as a fallback if you want
            # self.add_bubble_message(final_message, user_send=False)

        # 更新已收集步骤中的对应数据
        for step in self._agent_steps:
            if step['step_id'] == step_id:
                step['success'] = success
                step['message'] = message
                break

    def handle_agent_finished(self, final_message):
        """Receives Agent successful completion signal."""
        self.input_field.set_send_button_status(True)
        self.current_workflow_container = None  # 重置容器

        # 将 Agent 工作流步骤持久化到数据库
        if hasattr(self, 'conversation_repo') and self.conversation_repo:
            session_id = self.sendTask.assistant.session_id

            # 从 ReActAgentController 取出推理链
            self._react_thought_chain = list(
                getattr(self.agent_controller, '_thought_chain', [])
            )

            if self._agent_steps or self._react_thought_chain:
                workflow_content = make_agent_workflow_message(
                    role="assistant",
                    mode="react",
                    final_result=final_message,
                    steps=self._agent_steps,
                    thought_chain=self._react_thought_chain,
                )
                self.conversation_repo.add_message(session_id, 'assistant', workflow_content)
                self.conversation_repo.update_timestamp(session_id)
                logging.info(
                    f"[agent_persist] mode=react "
                    f"steps={len(self._agent_steps)} "
                    f"thoughts={len(self._react_thought_chain)} "
                    f"session={session_id[:8]}.."
                )

        # 清空步骤收集器
        self._agent_steps = []
        self._react_thought_chain = []

    def handle_agent_error(self, error_message):
        """Receives Agent error signal."""
        self.show_waiting_message(False)
        self.add_bubble_message(f"<b>❌ Workflow Error:</b><br>{error_message}", user_send=False)
        self.input_field.set_send_button_status(True)
        self.current_workflow_container = None  # 重置容器
        self._agent_steps.clear()
        self._react_thought_chain.clear()

    def send_quest_to_ai(self, message):
        self.current_input = message
        self.speech_page.updateStatus('等待中')
        if self.serverCheck.internet_status():
            # Speech.short_text_play("好的，请稍等")
            if self.current_func == "语种翻译":
                if self.input_field.language_layout.itemAt(0).widget().current_language == "自动":
                    detected_lang = TranslateDetect.detect_language(message)
                    self.input_field.language_layout.itemAt(0).widget().set_current_language(detected_lang)
                message = message+"[END]把用户输入翻译成"+self.input_field.language_layout.itemAt(2).widget().current_language

            print("send_quest_to_ai model is" + self.sendTask.assistant.model)
            self.sendTask.set_topic(message)
            self.sendTask.start()
        else:
            bubble_message = self.add_bubble_message("服务异常", False)
            bubble_message.play_button.hide()
            self.input_field.set_send_button_status(True)
            self.speech_page.updateStatus('休眠中')

    def handle_send_message(self, user_input, full_message, thumbnail_list):
        self.add_bubble_message(user_input, True, thumbnail_list=thumbnail_list)

        if self.contentStackWgt.currentWidget() != self.chat_box:
            self.contentStackWgt.setCurrentWidget(self.chat_box)
            # 当有对话时，隐藏背景logo
            self.chat_intro.hide()

        # 首次发消息时：创建数据库会话记录并设置标题
        if not hasattr(self, 'conversation_repo') or not self.conversation_repo:
            from database.repository.conversation_repository import ConversationRepository
            self.conversation_repo = ConversationRepository()
            self.sendTask.assistant.model_manager.set_conversation_repo(self.conversation_repo)
        conv = self.conversation_repo.get_conversation(self.sendTask.assistant.session_id)
        if not conv:
            # 首次发消息，创建数据库记录
            self.conversation_repo.create_conversation(
                self.sendTask.assistant.session_id,
                self.current_model,
                self.current_func
            )
            # 用第一条消息前20字作为标题
            title = user_input[:20] + ("..." if len(user_input) > 20 else "")
            self.conversation_repo.update_title(self.sendTask.assistant.session_id, title)

        if self.current_func == "AI Agent":
            # 开始新的 Agent 工作流前清空步骤收集器
            self._agent_steps.clear()
            self._react_thought_chain.clear()

            # 保存用户消息到数据库（统一 JSON 格式）
            session_id = self.sendTask.assistant.session_id
            user_json = make_text_message("user", user_input)
            self.conversation_repo.add_message(session_id, "user", user_json)

            # Show a generic waiting message immediately for better user feedback
            self.show_waiting_message(True)
            self.agent_thread.start()
            QMetaObject.invokeMethod(self.agent_controller, "start_workflow",
                                     Qt.QueuedConnection, Q_ARG(str, full_message))
            return

        # For all other functions, maintain the original logic
        if self.mode == AssistantMode.CHAT or self.mode == AssistantMode.MEETING:
            self.send_quest_to_ai(full_message)
        elif self.mode == AssistantMode.PAINT:
            self.send_paint_to_ai(full_message)
        else:
            self.add_bubble_message("会议纪要暂未实现", False)

    def handle_send_voice_message(self, message):
        if len(message) == 0:
            self.speech_page.updateStatus('休眠中')
            self.input_field.capture_voice_flag = False
            return

        self.add_bubble_message(message, True)
        
        # 当有对话时，切换到聊天框并隐藏背景logo
        if self.contentStackWgt.currentWidget() != self.chat_box:
            self.contentStackWgt.setCurrentWidget(self.chat_box)
            self.chat_intro.hide()

        if self.mode == AssistantMode.CHAT or self.mode == AssistantMode.MEETING:
            self.send_quest_to_ai(message)  # AI模型检索
        elif self.mode == AssistantMode.PAINT:
            self.send_paint_to_ai(message)  # 文字绘图
        else:
            print("Meeting")

    def add_bubble_message(self, message, user_send, thumbnail_list=None):
        self.chat_box.scrollArea.reset_auto_scroll()
        if thumbnail_list is not None and len(thumbnail_list) > 0:
            for thumbnail in thumbnail_list:
                thumbnail_message = ThumbnailMessage(user_send=user_send,thumbnail = thumbnail)
                self.chat_box.add_message_item(thumbnail_message)
        bubble_message = BubbleMessage(message, '', msg_type=MessageType.TEXT, font_size=12, user_send=user_send)
        self.chat_box.add_message_item(bubble_message)
        self.show_waiting_message(user_send)
        return bubble_message

    # 新建对话处理逻辑（清空旧的ChatTask+新建新的ChatTask）
    def new_dialog_handle(self):
        # 先保存当前对话（防止中途切换导致消息未持久化）
        self._save_current_conversation()

        # 清理旧的ChatTask
        if self.sendTask.isRunning():
            self.sendTask.stop()
            self.show_waiting_message(False)
            self.current_bubble_message = None
            self.input_field.set_send_button_status(True)

        # 清空内存中的历史（使用前保存）
        prev_session_id = self.sendTask.assistant.session_id
        if hasattr(self, 'conversation_repo') and self.conversation_repo:
            mm = self.sendTask.assistant.model_manager
            if prev_session_id in mm.memory:
                mm.memory[prev_session_id].clear()

        # 创建新的ChatTask
        self.sendTask = ChatTask()  # 新实例化一个Assistant
        self.sendTask.complete_signal.connect(self.ai_callback)
        self.sendTask.update_signal.connect(self.update_ai_message)

        # 懒加载 ConversationRepository 并注入 ModelManager
        if not hasattr(self, 'conversation_repo'):
            from database.repository.conversation_repository import ConversationRepository
            self.conversation_repo = ConversationRepository()
        self.sendTask.assistant.model_manager.set_conversation_repo(self.conversation_repo)

        # 重置界面
        self.workflow_step_widgets.clear()
        self.current_workflow_container = None

        self.chat_box.clearLayout()
        self.input_field.show()
        self.chat_intro.show()
        self.shift2home_page()
        self.model_select_btn.set_current_model("DeepSeek-V3")
        self.voice_message = ""
        logging.info(f'新建对话会话ID：{self.sendTask.assistant.session_id}')

    def _save_current_conversation(self):
        """将当前对话的内存历史写入数据库（增量写入，过滤 system，清理前缀）"""
        if not hasattr(self, 'conversation_repo') or not self.conversation_repo:
            return
        session_id = self.sendTask.assistant.session_id
        mm = self.sendTask.assistant.model_manager
        history = mm.memory.get(session_id)
        if not history or not history.messages:
            # 即使内存中没有消息，也检查是否有未完成的 Agent 工作流需要保存
            self._save_incomplete_agent_workflow(session_id)
            return
        # 检查 DB 中是否已有该会话记录
        conv = self.conversation_repo.get_conversation(session_id)
        if not conv:
            return
        # 只比较 user/assistant 消息，跳过 system 消息
        mem_msgs = [m for m in history.messages if m.type in ("human", "ai")]
        if not mem_msgs:
            self._save_incomplete_agent_workflow(session_id)
            return
        db_messages = self.conversation_repo.get_messages(session_id)
        db_count = len(db_messages)
        logging.info(f"[_save_conv] session={session_id[:8]}.. memory_msgs={len(mem_msgs)} db_msgs={db_count}")
        if len(mem_msgs) > db_count:
            for msg in mem_msgs[db_count:]:
                role = "user" if msg.type == "human" else "assistant"
                raw_content = msg.content
                if role == "user" and raw_content.startswith("用户输入："):
                    raw_content = raw_content[len("用户输入："):]
                    if raw_content.endswith('\n'):
                        raw_content = raw_content[:-1]
                content = make_text_message(role, raw_content)
                logging.info(f"[_save_conv]   -> writing role={role}, text_preview={raw_content[:20]!r}")
                self.conversation_repo.add_message(session_id, role, content)

            # 保存未完成的 Agent 工作流（如果有）
            self._save_incomplete_agent_workflow(session_id)

            # 只有实际写入了新消息，才更新时间戳
            self.conversation_repo.update_timestamp(session_id)
        else:
            # 没有新消息写入，仅保存未完成的 Agent 工作流
            self._save_incomplete_agent_workflow(session_id)

    def _save_incomplete_agent_workflow(self, session_id: str):
        """保存尚未完成的 Agent 工作流步骤（切换功能/新建对话时调用）"""
        if not hasattr(self, '_agent_steps') or not self._agent_steps:
            return
        conv = self.conversation_repo.get_conversation(session_id)
        if not conv:
            return
        # 检查是否已经有 agent workflow 消息（避免重复保存）
        db_messages = self.conversation_repo.get_messages(session_id)
        for msg in db_messages:
            if msg.role == "assistant" and is_json_message(msg.content):
                data = parse_message_content(msg.content)
                if data.get("type") == "agent_workflow":
                    return  # 已有工作流消息，不重复保存
        # 保存未完成的工作流
        self._react_thought_chain = list(
            getattr(self.agent_controller, '_thought_chain', [])
        )
        workflow_content = make_agent_workflow_message(
            role="assistant",
            mode="react",
            final_result='（工作流被中断）',
            steps=self._agent_steps,
            thought_chain=self._react_thought_chain,
        )
        self.conversation_repo.add_message(session_id, 'assistant', workflow_content)
        logging.info(f"[_save_incomplete_agent] Saved {len(self._agent_steps)} steps for interrupted workflow")
        self._agent_steps.clear()
        self._react_thought_chain.clear()

    def open_history_conversation(self, conversation_id: str):
        """打开历史对话，恢复上下文"""
        # 懒加载 ConversationRepository（首次打开历史时可能尚未初始化）
        if not hasattr(self, 'conversation_repo') or not self.conversation_repo:
            from database.repository.conversation_repository import ConversationRepository
            self.conversation_repo = ConversationRepository()

        # 1. 加载会话元数据
        conv = self.conversation_repo.get_conversation(conversation_id)
        if not conv:
            return

        # 2. 先保存当前对话
        self._save_current_conversation()

        # 3. 停止当前任务
        if self.sendTask.isRunning():
            self.sendTask.stop()
            self.show_waiting_message(False)
            self.current_bubble_message = None

        # 4. 切换到对应功能页面
        self.handle_function_selection(conv.function_type)

        # 5. 切换模型
        if conv.model_name:
            self.switch_model(conv.model_name)

        # 6. 创建新的 ChatTask，复用原有 session_id
        self.sendTask = ChatTask()
        self.sendTask.assistant.session_id = conversation_id
        self.sendTask.assistant.model_manager.set_conversation_repo(self.conversation_repo)
        self.sendTask.complete_signal.connect(self.ai_callback)
        self.sendTask.update_signal.connect(self.update_ai_message)

        # 7. 从 DB 加载历史消息到内存
        db_messages = self.conversation_repo.get_messages(conversation_id)
        mm = self.sendTask.assistant.model_manager
        history = mm.get_session_history(conversation_id)
        history.clear()  # 确保内存历史是干净的
        for msg in db_messages:
            if msg.role not in ("user", "assistant"):
                continue
            text = get_text_content(msg.content)
            if msg.role == "user":
                history.add_user_message(text)
            elif msg.role == "assistant":
                history.add_ai_message(text)

        logging.info(f"[restore] db_messages count={len(db_messages)}, roles={[m.role for m in db_messages]}")
        # 8. 清空 UI，重新渲染历史气泡（跳过 system 消息）
        self.workflow_step_widgets.clear()
        self.current_workflow_container = None
        self._agent_steps.clear()
        self._react_thought_chain.clear()
        self.chat_box.clearLayout()
        for msg in db_messages:
            if msg.role not in ("user", "assistant"):
                continue

            data = parse_message_content(msg.content)
            msg_type = data.get("type", "text")

            if msg_type == "agent_workflow":
                # Agent 工作流 → AgentHistoryWidget
                agent_mode = data.get("mode", "react")
                final_result = data.get("final_result", "")
                steps = data.get("steps", [])
                thought_chain = data.get("thought_chain")
                widget = AgentHistoryWidget(final_result, steps, agent_mode, thought_chain)
                self.chat_box.add_message_item(widget)

            elif msg_type == "text":
                # 普通文本 → BubbleMessage
                text_content = data.get("content", msg.content)
                bubble = BubbleMessage(
                    text_content, '', MessageType.TEXT,
                    font_size=12, user_send=(msg.role == "user")
                )
                self.chat_box.add_message_item(bubble)

            else:
                # 未知类型，兜底渲染为普通文本
                fallback = data.get("content", msg.content) if isinstance(data, dict) else msg.content
                bubble = BubbleMessage(
                    fallback, '', MessageType.TEXT,
                    font_size=12, user_send=(msg.role == "user")
                )
                self.chat_box.add_message_item(bubble)

        # 9. 确保 chat_box 显示在界面上
        self.chat_intro.hide()
        self.chat_box.show()
        if self.contentStackWgt.indexOf(self.chat_box) == -1:
            self.contentStackWgt.addWidget(self.chat_box)
        self.contentStackWgt.setCurrentWidget(self.chat_box)
        self.input_field.show()
        self.model_select_btn.set_current_model(conv.model_name or "DeepSeek-V3")

        # 10. 恢复 ReAct 推理链（从工作流数据中提取）
        if conv.function_type == "AI Agent":
            self.input_field.agent_mode_button.set_mode("react")
            for msg in db_messages:
                data = parse_message_content(msg.content)
                if data.get("type") == "agent_workflow":
                    self._react_thought_chain = data.get("thought_chain", []) or []
                    break

        # 11. 更新标题（显示功能名称，与正常使用时一致）
        self.title_change_requested.emit(conv.function_type)

        logging.info(f'恢复历史对话会话ID：{conversation_id}')

    def update_selected_kb(self, selected_kb_id_list):
        self.selected_kb_id_list = selected_kb_id_list
        self.sendTask.assistant.set_selected_kb(selected_kb_id_list)

    def delete_index_history(self, con):
        # TODO
        # if hasattr(self, "sendTask") and self.sendTask is not None:
        #     success = self.sendTask.assistant.model_manager.remove_session_history_by_content( self.sendTask.assistant.session_id,con)
        #     if success:
        #         print(f"已成功删除 sendTask 历史记录中{con}")
        #     else:
        #         print(f"删除 sendTask 历史记录失败，{con} 不存在")
        return

    # Send End

    def set_chat_mode(self):
        print("Chat mode now.")
        self.mode = AssistantMode.CHAT

    def set_draw_mode(self):
        print("Paint mode now.")
        self.mode = AssistantMode.PAINT

    def set_meeting_mode(self):
        print("Meeting mode now.")
        self.mode = AssistantMode.MEETING

    def shift2home_page(self):
        self.set_chat_mode()
        self.handle_function_selection("智能问答")

    # Speech Start
    def listeningToWaiting(self):  # 聆听中到等待中的自动转换函数
        if self.voice_message != self.last_voice_message:
            self.last_voice_message = self.voice_message
        else:
            self.speech_page.capture_voice()
            # self.speech_page.updateStatus('等待中')

    def internet_change_handle(self, status):
        if status:
            self.input_field.set_microphone_button_status(True)
        else:
            self.input_field.set_microphone_button_status(False)

    def handle_speech(self, flag, message, bubble_message):
        if not flag:
            self.speechTask.stop_speech()
        else:
            self.speechTask.set_message(message, bubble_message)
            self.speechTask.start()

    def stop_speech_signal_exchange(self):
        self.speechTask.stop_speech()

    def speechTaskCallback(self, bubble_message):
        print("speechTaskCallback")
        bubble_message.playComplete()
        self.speech_page.updateStatus('休眠中')

    # Speech End

    # Voice Start
    def receive_voice_message(self, message):
        self.voice_message += message
        self.input_field.set_input_text(self.voice_message)

    def handle_capture_voice(self):
        print("handle_capture_voice")
        if self.input_field.capture_voice_flag:
            self.input_field.capture_voice_flag = False
            self.voiceInput.stop_recognition()
            self.handle_send_voice_message(self.voice_message)
            self.timerSend.stop()
            self.voice_message = ""
            self.input_field.set_input_text("")
        else:
            self.input_field.capture_voice_flag = True
            self.voiceInput.start()
            self.timerSend.start(3000)
            self.voice_message = ""
            self.input_field.set_input_text("")

    # Voice End

    # Drawing Start
    def send_paint_to_ai(self, message):
        if self.serverCheck.internet_status():
            # 文字绘图
            self.speechTask.set_message("好的，请稍等")
            self.speechTask.start()
            self.aiDrawingTask.set_prompt(message)
            self.aiDrawingTask.start()
            self.aiDrawingTask.start_timer(30000)
        else:
            bubble_message = self.add_bubble_message("无法连接互联网服务，请检查网络", False)
            bubble_message.play_button.hide()
            self.input_field.set_send_button_status(True)

    def complete_drawing_handle(self, file_path):
        self.show_waiting_message(False)
        if "fail:" in file_path:
            bubble_message = BubbleMessage(file_path, '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
            self.chat_box.add_message_item(bubble_message)
            bubble_message.play_button.hide()
        else:
            bubble_message = BubbleMessage(file_path, '', msg_type=MessageType.IMAGE, font_size=12, user_send=False)
            self.chat_box.add_message_item(bubble_message)
            Speech.short_text_play("绘图完成")

        self.input_field.set_send_button_status(True)

    # Drawing End

    # 会议功能 start
    def show_meeting_waiting_message(self, show):  # 总是和BubbleMessage成对出现，send为True则显示，否则隐藏，待优化
        if show:
            self.meetingWgt.add_message_item(self.waitingMeetingMessage)
            self.waitingMeetingMessage.show()
        else:
            self.meetingWgt.remove_message_item(self.waitingMeetingMessage)
            self.waitingMeetingMessage.hide()

    def meeting_service_status_handle(self, status):
        print(status)
        message = status
        self.meetingTask.status = "StartFail"
        self.show_meeting_waiting_message(False)
        if "Timeout" in status and "https://tingwu.cn-beijing.aliyuncs.com" in status:
            message = "连接服务器超时，请检查网络环境..."
        if "Failed to connect to host or proxy" in status:
            message = "连接服务器失败，请检查网络环境..."
        if "create transcriber request fail." in status:
            message = "创建会议记录请求失败..."
        if "transcriber request start fail." in status:
            message = "会议记录请求启动失败..."
        if "transcriber request start fail." in status:
            message = "会议记录请求启动超时..."
        if "open default PCM device fail." in status:
            message = "打开语音输入设备失败..."
        if "send audio fail" in status:
            message = "发送音频流失败，请检查网络环境..."

        bubble_message = BubbleMessage(message, '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
        bubble_message.message.meeting_content_adjust_size()
        self.meetingWgt.add_message_item(bubble_message)
        bubble_message.play_button.hide()
        self.meeting_bottom_ui.meeting_switch_handel()

    def meeting_message_ready_handle(self, message):
        self.show_meeting_waiting_message(False)
        if "StartFail" in self.meetingTask.status:
            self.meetingTask.status = ""
            return
        else:
            bubble_message = BubbleMessage(message, '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
            # bubble_message.speech_signal.connect(self.handle_speech)
            bubble_message.message.meeting_content_adjust_size()
            self.meetingWgt.add_message_item(bubble_message)
            bubble_message.play_button.hide()
            self.show_meeting_waiting_message(True)
            if "您已结束会议，会议纪要文件" not in message:
                MeetingFile.write_temp_file(message)

    def start_meeting(self):
        self.meetingTask.start()
        self.meetingTask.start_task()
        self.timer.stop()

    def meeting_signal_handle(self, status):
        if status:
            self.meetingTask.close_bin_process()
            self.meetingTask.exec_bin_process()
            self.timer.start(500)
            self.show_meeting_waiting_message(True)
        else:
            self.meetingTask.stop_task()
            self.show_meeting_waiting_message(False)
    # 会议功能 End

    def set_websearch_enabled(self, enabled):
        if hasattr(self, 'sendTask'):
            self.sendTask.set_websearch_enabled(enabled)

    def switch_model(self, model):
        """传入模型名，如Qwen-Max、DeepSeek-V3，非中文名"""
        self.current_model = model
        self.agent_controller.switch_model(model)
        self.sendTask.assistant.switch_model(model)

    def handle_gen_ppt(self,full_path):
        thumbnail_message = ThumbnailMessage(user_send=False,file_path =full_path)
        self.chat_box.scrollArea.reset_auto_scroll()
        self.chat_box.add_message_item(thumbnail_message)


# 菜单
class SettingMenu(QMenu):
    def __init__(self, *args, **kwargs):
        super(SettingMenu, self).__init__()
        self.radius = 10
        self.setting_menu_sytle = '''
            QMenu {{
                /* 半透明效果 */
                border-radius: {radius};
                border: 2px solid rgb(255, 255, 255);
                background-color: rgba(255, 255, 255, 230);
            }}
            QMenu::item {{
                border-radius: {radius};
                /* 这个距离很麻烦需要根据菜单的长度和图标等因素微调 */
                padding: 8px 48px 8px 12px; /* 12px是文字距离左侧距离*/
                background-color: transparent;
            }}

            /* 鼠标悬停和按下效果 */
            QMenu::item:selected {{
                border-radius: {radius};
                /* 半透明效果 */
                background-color: rgba(230, 240, 255, 232);
            }}

            /* 禁用效果 */
            QMenu::item:disabled {{
                border-radius: {radius};
                background-color: transparent;
            }}

            /* 图标距离左侧距离 */
            QMenu::icon {{
                left: 15px;
            }}

            /* 分割线效果 */
            QMenu::separator {{
                height: 1px;
                background-color: rgb(232, 236, 243);
            }}'''.format(radius=self.radius)
        self.setStyleSheet(self.setting_menu_sytle)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

    def setSubMenu(self):
        self.sub_menu.setStyleSheet(self.setting_menu_sytle)
        self.sub_menu.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)


# 标题栏
class MainWinTitle(QWidget):
    def __init__(self, title_height, parent=None):
        super(MainWinTitle, self).__init__(parent)
        self.title_height = title_height
        self.init_ui()

    def init_ui(self):
        self.setFixedHeight(self.title_height)
        self.setObjectName('title')
        self.setStyleSheet(
            '''
            #title{
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                background:transparent;
            }
            '''
        )
        self.setAttribute(Qt.WA_StyledBackground)
        self.installEventFilter(self)

        self.icon = QLabel(self)
        self.icon.setFixedSize(24, 24)
        self.icon.setScaledContents(True)
        self.icon.setPixmap(QPixmap(ConfigManager().app_config['logo']))
        self.icon.mousePressEvent = lambda event: self.parent().icon_clicked_event()

        self.title_name = QLabel(f"{ConfigManager().app_config['name']}")
        self.title_name.mousePressEvent = lambda event: self.parent().icon_clicked_event()
        font = QFont("Microsoft YaHei", 16)
        font.setWeight(QFont.Bold)
        self.title_name.setFont(font)
        self.title_name.setStyleSheet(
            '''
            color:white;
            '''
        )

        self.title_layout = QHBoxLayout(self)
        self.title_layout.setContentsMargins(18, 12, 18, 0)
        self.title_layout.addWidget(self.icon)
        self.title_layout.addWidget(self.title_name)
        self.title_layout.addItem(QSpacerItem(40, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

    def switchViewType(self, mode: ViewMode):
        """根据显示模式调整标题栏外观"""
        if mode == ViewMode.SIDEBAR:
            # --- 侧边栏模式：显示自定义标题栏 ---
            self.show()
            self.setFixedHeight(self.title_height)
            self.title_layout.setContentsMargins(18, 12, 18, 0)
            self.setStyleSheet(
                '''
                #title{
                    border-top-left-radius: 5px;
                    border-top-right-radius: 5px;
                    background:transparent;
                }
                '''
            )
            self.icon.setFixedSize(24, 24)
            self.icon.setPixmap(QPixmap(ConfigManager().app_config['logo']))
            self.icon.setScaledContents(True)
            self.title_name.setStyleSheet(
                '''
                color:white;
                font-size:16px;
                font-weight:bold;
                '''
            )
            self.title_layout.setSpacing(10)
        elif mode == ViewMode.WINDOW:
            self.show()
            self.setFixedHeight(self.title_height)
            self.title_layout.setContentsMargins(18, 12, 18, 0)
            self.setStyleSheet(
                '''
                #title{
                    border-top-left-radius: 5px;
                    border-top-right-radius: 5px;
                    background:transparent;
                }
                '''
            )
            self.icon.setFixedSize(36, 36)
            self.icon.setPixmap(QPixmap(ConfigManager().app_config['logo']))
            self.icon.setScaledContents(True)
            self.title_name.setStyleSheet(
                '''
                color:white;
                font-size:16px;
                font-weight:bold;
                '''
            )
            self.title_layout.setSpacing(10)
