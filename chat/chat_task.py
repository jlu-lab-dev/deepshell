from PyQt5.QtCore import QThread, pyqtSignal
from chat.assistant import Assistant


class ChatTask(QThread):
    complete_signal = pyqtSignal(str)  # 用于通知完成
    update_signal = pyqtSignal(str)  # 用于流式更新内容

    def __init__(self, assistant_type='general'):
        super().__init__()
        self.topic = ""
        self.assistant = Assistant(assistant_type)
        self.stop_flag = False    # 对话停止标志

    def set_topic(self, topic):
        self.topic = topic

    def run(self):
        try:
            # 用于累积完整响应
            self.stop_flag = False

            complete_response = ""

            # 流式处理响应
            for chunk in self.assistant.chat_stream([self.topic]):
                if self.stop_flag:
                    break
                complete_response += chunk
                # 发送更新信号，用于更新UI
                self.update_signal.emit(complete_response)

            if not self.stop_flag:
                self.complete_signal.emit(complete_response)

        except Exception as e:
            print(f"ChatTask exception: {e}")
            complete_response = "模型对话失败，请检查模型配置或网络连接！"
            self.complete_signal.emit(complete_response)

    def stop(self):
        """停止线程"""
        self.stop_flag = True
        self.quit()  # 调用 QThread 的 quit 方法
        self.wait()  # 等待线程结束