import json
import logging
import re
from enum import Enum
import datetime
import PyQt5.sip as sip
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget, QStackedWidget, QHBoxLayout, QVBoxLayout, QSpacerItem, QSizePolicy, QMenu, QLabel

from ai_audio.audio_task import AudioTask
from ai_table.gen_report import generate_analyst_report
from ai_table.gen_table import generate_table
from ai_table.intro_ui import TableIntroPage
from ai_table.table_task import TableTask
from audio_transcription.intro_ui import AudioTranscriptionIntroPage
from meeting.intro_ui import MeetingIntroPage
from mind_map.intro_ui import MindMapIntroPage
from ppt.intro_ui import PPTIntroPage
from sys_agent.intro_ui import SysFuncIntro
from sys_agent.sys_func_call import FUNCTION_MAP
from sys_agent.sys_agent_task import SysAgentExplanationTask, SysAgentFunctionCallTask
from translation.intro_ui import TranslateIntroPage
from ui.chat.bubble_message import BubbleMessage, MessageType, TextMessage ,ThumbnailMessage,ButtonMessage
from meeting.meeting_box import MeetingWidget
from ui.chat.chat_box import ChatBox
from chat.chat_task import ChatTask
from chat.intro_page import ChatIntroPage
from speech.voice_recognition import VoiceRecognition
from speech.speech_task import Speech, SpeechTask
from ui.button.knowledge_base_select_button import KnowledgeBaseSelectButton
from ui.button.model_select_button import ModelSelectButton
from utils.intro_ui import DocAnalysisIntroPage
from utils.open_local_app_task import OpenLocalAppTask
from draw.drawing_task import AiDrawingTask
from server_check import ServerCheck
from meeting.meeting_btn_widget import MeetingBottomWidget
from meeting.meeting_task import MeetingTask, MeetingFile
from ui.page.speech_page import SpeechPage
from ui.button.function_menu_button import FunctionMenuButton
from ui.input_field import InputField
from ui.knowledge_base.knowledge_base_home import KnowledgeBaseHome
from ocr.intro_ui import OcrIntroPage
from ui.button.new_dialog_button import NewDialogButton
from ppt.workflow.ppt_task import PPTTask
from utils.workflow.document_task import DocumentTask
from config.config_manager import ConfigManager
from ocr.ocr_task import OcrTask
from translation.translate_task import TranslateTask
from mind_map.map_task import MAPTask
from audio_transcription.transcriptionTask import TranscriptionTask
from translation.translate_detect import TranslateDetect
from ppt.makePPTByTemplate.mdtojson import PPTGenerator

# app_list = '[{"打开系统设置": "found-control-center"}, {"打开应用商店": "ai-assistant open-appstore"}, {"打开视频播放器": "ai-assistant open-video-player"},  {"打开浏览器": "nfs-browser"},{"打开文本编辑器":"ai-assistant open-txt"}, {"打开日历":"ai-assistant open-calender"},{"调高音量":"ai-assistant  set-volume-up"},{"调低音量":"ai-assistant  set-volume-down"},{"调高屏幕亮度":"ai-assistant  set-brightness-up"},{"调低屏幕亮度":"ai-assistant  set-brightness-down"},{"打开登录密码设置":"ai-assistant set-password"},{"打开屏幕分辨率设置":"ai-assistant set-display"},{"打开默认程序设置":"ai-assistant set-default-apps"},{"打开系统主题设置":"ai-assistant set-theme"},{"打开字体设置":"ai-assistant set-font"},{"打开系统音量设置":"ai-assistant set-sound"},{"打开系统时间设置":"ai-assistant set-datetime"},{"打开节能模式设置":"ai-assistant set-powersave-mode"},{"打开锁屏时间设置":"ai-assistant set-lock"},{"查询系统版本信息":"ai-assistant get-system-info"},{"查询CPU信息":"ai-assistant get-cpu-info"},{"查询内核版本":"ai-assistant get-kernel-info"},{"查询内存信息":"ai-assistant get-memory-info"},{"打开壁纸设置":"ai-assistant set-background"},{"打开网络设置":"ai-assistant set-network"},{"打开屏保设置":"ai-assistant set-screensaver"},{"打开邮箱":"ai-assistant open-email"},{"打开系统帮助":"ai-assistant open-system-help"},{"打开文件管理器":"ai-assistant open-file-manager"},{"打开资源监视器":"ai-assistant open-stacer"},{"打开文档查看器":"ai-assistant open-document-viewer"},{"打开终端":"ai-assistant open-terminal"},{"打开压缩工具":"ai-assistant open-file-compress"},{"打开计算器":"ai-assistant open-calculator"},{"打开wifi设置":"ai-assistant set-wifi"},{"打开蓝牙设置":"ai-assistant set-bluetooth"},{"打开画板":"ai-assistant open-drawing-board"},{"关闭画板":"killall nfs-drawing"},{"关闭应用商店":"ai-assistant close-appstore"},{"关闭视频播放器":"ai-assistant close-video-player"},{"打开音乐播放器":"ai-assistant open-music"},{"关闭音乐播放器":"ai-assistant close-music"},{"关闭文本编辑器":"ai-assistant close-txt"},{"关闭计算器":"ai-assistant close-calculator"},{"关闭系统设置":"killall found-control-center"},{"关闭浏览器":"killall nfs-browser"},{"关闭终端":"killall gnome-terminal-server"},{"关闭资源监视器":"killall stacer"},{"关闭邮箱":"killall thunderbird"},{"关闭wifi设置":"killall found-control-center"},{"关闭蓝牙设置":"killall blueman-manager"},{"关闭系统帮助":"killall evince"}, {"打开摄像头工具":"cheese"},{"关闭摄像头工具":"killall cheese"}]'
# app_list = json.loads(app_list)


logging.basicConfig(level=logging.INFO)


class AssistantMode(Enum):
    """
        会议记录时AI助手为meeting模式，界面切换为meeting box，发送的消息类型MessageType是TEXT
        其他时候AI助手均为chat模式，界面切换为chat box，发送的消息可能是TEXT、IMAGE、TABLE
    """
    CHAT = "chat"
    MEETING = "meeting"


class MainWin(QWidget):
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

        self.chat_box = ChatBox(432, self.main_win_height - 250)  # 聊天框
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
        hor_layout.addWidget(self.new_dialog_btn)
        hor_layout.addStretch()
        hor_layout.addWidget(self.knowledge_base_select_btn)
        hor_layout.addStretch()
        hor_layout.addWidget(self.model_select_btn)
        hor_layout.addStretch()
        hor_layout.addWidget(self.function_menu_btn)
        # 功能按钮 End

        # 底部按钮栈 Start
        self.bottomStackWgt = QStackedWidget()

        self.input_field = InputField()
        self.input_field.hide()
        self.input_field.send_signal.connect(self.handle_send_message)

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
            # "语种翻译": {
            #     "main": self.translate_intro,
            #     "chat": self.chat_box,
            #     "bottom": self.input_field,
            # },
            # "AI 识图": {
            #     "main": self.ocr_intro,
            #     "chat": self.chat_box,
            #     "bottom": self.input_field
            # },
            # "文档分析": {
            #     "main": self.doc_analysis_intro,
            #     "chat": self.chat_box,
            #     "bottom": self.input_field,
            # },
            "知识库": {
                "main": self.knowledge_base_home
            },
            # "AI 表格": {
            #     "main": self.table_intro,
            #     "chat": self.chat_box,
            #     "bottom": self.input_field,
            # },
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
            "系统功能": {
                "main": self.sys_func_intro,
                "chat": self.chat_box,
                "bottom": self.input_field,
            }
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
        self.chain_step = 1
        self.tool_result = []

        # web search setting
        self.enable_websearch = False

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

    def handle_function_selection(self, function_name):
        """集中处理功能切换时的UI"""
        config = self.page_mapping.get(function_name)
        if function_name != "知识库":
            self.parent().change_title_midlabel(function_name)
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
            case "系统功能":
                self.mode = AssistantMode.CHAT
                self.sendTask = SysAgentExplanationTask()
            # case "AI 表格":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = TableTask()
            # case "AI 识图":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = OcrTask()
            case "会议记录":
                self.mode = AssistantMode.CHAT
                self.sendTask = AudioTask()
            # case "语种翻译":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = TranslateTask()
            case "思维导图":
                self.mode = AssistantMode.CHAT
                self.sendTask = MAPTask()
            # case "音频转写":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = TranscriptionTask()
            # case "文档分析":
            #     self.mode = AssistantMode.CHAT
            #     self.sendTask = DocumentTask()
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
            elif self.current_func == "系统功能":
                self.current_bubble_message = BubbleMessage(result, '', msg_type=MessageType.TEXT, font_size=12, need_button=False, user_send=False)
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
            elif self.current_func == "系统功能":
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

        if self.current_func == "系统功能":
            # 如果还没有加载动画气泡，则添加
            result_bubble = BubbleMessage(f'正在拆解为子任务链...', '', msg_type=MessageType.TEXT, font_size=12, user_send=False)
            self.chat_box.add_message_item(result_bubble)
            self.tool_result = []
            self.chain_step = 1
            self.start_function_call_chain(self.current_input, self.tool_result, result_bubble)

        # 重置当前BubbleMessage引用
        self.current_bubble_message = None
        # 启用发送按钮
        self.input_field.set_send_button_status(True)

    def send_quest_to_ai(self, message):
        self.current_input = message
        self.speech_page.updateStatus('等待中')
        if self.serverCheck.internet_status():
            # Speech.short_text_play("好的，请稍等")
            if self.current_func == "语种翻译":
                if self.input_field.language_layout.itemAt(0).widget().current_language == "自动检测":
                    detected_lang = TranslateDetect.detect_language(message)
                    self.input_field.language_layout.itemAt(0).widget().set_current_language(detected_lang)
                message = message+"[END]把用户输入翻译成"+self.input_field.language_layout.itemAt(2).widget().current_language
            
            self.sendTask.set_topic(message)
            self.sendTask.start()
        else:
            bubble_message = self.add_bubble_message("服务异常", False)
            bubble_message.play_button.hide()
            self.input_field.set_send_button_status(True)
            self.speech_page.updateStatus('休眠中')

    def handle_send_message(self, user_input, full_message, thumbnail_list):
        # 判断当前页面如果是gui就跳转聊天
        self.add_bubble_message(user_input, True, thumbnail_list=thumbnail_list)

        if self.mode == AssistantMode.CHAT or self.mode == AssistantMode.MEETING:  # AI模型检索
            if self.contentStackWgt.currentWidget() != self.chat_box:
                self.contentStackWgt.setCurrentWidget(self.chat_box)
            self.send_quest_to_ai(full_message)
        elif self.mode == AssistantMode.PAINT:  # 文字绘图
            self.send_paint_to_ai(full_message)
        else:  # 会议纪要
            self.add_bubble_message("会议纪要暂未实现", False)

    def handle_send_voice_message(self, message):
        if len(message) == 0:
            self.speech_page.updateStatus('休眠中')
            self.input_field.capture_voice_flag = False
            return

        self.add_bubble_message(message, True)

        if self.mode == AssistantMode.CHAT or self.mode == AssistantMode.MEETING:
            self.send_quest_to_ai(message)  # AI模型检索
        elif self.mode == AssistantMode.PAINT:
            self.send_paint_to_ai(message)  # 文字绘图
        else:
            print("Meeting")

    def add_bubble_message(self, message, user_send, thumbnail_list=None):
        self.chat_box.scrollArea.reset_auto_scroll()
        if len(thumbnail_list) > 0:
            for thumbnail in thumbnail_list:
                thumbnail_message = ThumbnailMessage(user_send=user_send,thumbnail = thumbnail)
                self.chat_box.add_message_item(thumbnail_message)
        bubble_message = BubbleMessage(message, '', msg_type=MessageType.TEXT, font_size=12, user_send=user_send)
        self.chat_box.add_message_item(bubble_message)
        self.show_waiting_message(user_send)
        return bubble_message

    # 新建对话处理逻辑（清空旧的ChatTask+新建新的ChatTask）
    def new_dialog_handle(self):
        # 清理旧的ChatTask
        if self.sendTask.isRunning():
            self.sendTask.stop()
            self.show_waiting_message(False)
            self.current_bubble_message = None
            self.input_field.set_send_button_status(True)

        # 创建新的ChatTask
        self.sendTask = ChatTask()  # 新实例化一个Assistant
        self.sendTask.complete_signal.connect(self.ai_callback)
        self.sendTask.update_signal.connect(self.update_ai_message)

        # 重置界面
        self.chat_box.clearLayout()
        self.input_field.show()
        self.chat_intro.show()
        self.shift2home_page()
        self.model_select_btn.set_current_model("DeepSeek-V3")
        self.voice_message = ""
        logging.info(f'新建对话会话ID：{self.sendTask.assistant.session_id}')

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

    # system agent function calling chain START
    def start_function_call_chain(self, user_input, tool_result, result_bubble):
        content = user_input + "\n工具调用结果：" + "\n".join(
            f"{json.dumps(item, ensure_ascii=False)}" for item in tool_result
        ) if len(tool_result) > 0 else user_input
        logging.info(content)
        self.function_call_task = SysAgentFunctionCallTask()
        self.function_call_task.update_signal.connect(self.update_function_calling_chain)
        self.function_call_task.complete_signal.connect(lambda message: self.function_calling_chain_callback(message, result_bubble))
        self.function_call_task.set_topic(content)
        self.function_call_task.start()

    def update_function_calling_chain(self, message):
        """function_call_task输出调用工具链的进度"""
        self.input_field.set_send_button_status(False)

    def function_calling_chain_callback(self, message, result_bubble):
        """调用工具链生成完毕"""        
        actions = json.loads(message.strip())
        if isinstance(actions, dict):  # 单步
            actions = [actions]
        logging.info(actions)
        try:
            need_more_tool = False
            for action in actions:
                tool_name = action.get("tool")
                args = action.get("args", {})
                need_more_tool |= action.get("need_more_tool", False)

                result_bubble.message.update_text(result_bubble.message.text() + "<br>" + f"正在执行第{self.chain_step}个子任务...")
                if tool_name and tool_name in FUNCTION_MAP:
                    func = FUNCTION_MAP[tool_name]
                    result = func(**args)
                    # 将tool_name字段放到字典最前面
                    from collections import OrderedDict
                    result = OrderedDict([('tool_name', tool_name), *result.items()])
                    self.tool_result.append(result)
                    logging.info(result)
                    if result["success"]:
                        msg = f'子任务{self.chain_step} 执行【成功】：\n{result["message"]}'
                    else:
                        msg = f'执行【失败】：\n{result["message"]}'
                    if result.get("data") is not None:
                        data = result["data"]
                        if isinstance(data, list):
                            msg += "<br>" + "<br>".join(str(item) for item in data)
                        elif isinstance(data, dict):
                            msg += "<br>" + "<br>".join(f"{k}: {v}" for k, v in data.items())
                        else:
                            msg += "<br>" + str(data)
                else:
                    msg = "执行【失败】：\n无法识别的操作或无效的工具名。"
                
                result_bubble.message.update_text(result_bubble.message.text() + msg.replace('\n', '<br>'))
                self.chain_step += 1

            if need_more_tool:
                self.start_function_call_chain(self.current_input, self.tool_result, result_bubble)
            else:
                result_bubble.message.update_text(result_bubble.message.text() + "<br>" + "操作已全部完成")
        
        except Exception as e:
            msg = f"执行【失败】：\n{str(e)}"
            result_bubble.message.update_text(result_bubble.message.text() + msg.replace('\n', '<br>'))
        finally:
            result_bubble.speech_signal.connect(self.handle_speech)
            result_bubble.update_button_status(True)
            
            self.chat_box.scrollArea.reset_auto_scroll()
            self.input_field.set_send_button_status(True)
    
    # system agent function calling chain END

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

    def switch_model(self, model):
        """传入模型名，如Qwen-Max、DeepSeek-V3，非中文名"""
        self.current_model = model
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
        self.title_name.setStyleSheet(
            '''
            color:white;
            font-size:16px;
            '''
        )

        self.title_layout = QHBoxLayout(self)
        self.title_layout.setContentsMargins(18, 12, 18, 0)
        self.title_layout.addWidget(self.icon)
        self.title_layout.addWidget(self.title_name)
        self.title_layout.addItem(QSpacerItem(40, 10, QSizePolicy.Expanding, QSizePolicy.Minimum))

    def switchViewType(self):
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