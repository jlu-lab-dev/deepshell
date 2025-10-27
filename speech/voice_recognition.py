# For prerequisites running the following sample, visit https://help.aliyun.com/document_detail/611472.html
import json
import sys
from PyQt5.QtCore import QThread, pyqtSignal
import pyaudio
import dashscope
from dashscope.audio.asr import (Recognition, RecognitionCallback,
                                 RecognitionResult)

from config.config_manager import ConfigManager

config_manager = ConfigManager()
dashscope.api_key = config_manager.get_online_api_key("阿里云百炼")

mic = None  #管理麦克风对象pyaudio.PyAudio
stream = None


class VoiceCallback(RecognitionCallback):
    stop_flag=False

    def __init__(self):
        super().__init__()
        self.openAudioSuccess = False
        self.input_voice_message = ""
        self.last_text = ""  # 记录上次输出的内容

    def on_open(self) -> None:
        global mic
        global stream
        print('RecognitionCallback open.')
        try:
            mic = pyaudio.PyAudio()
            print('RecognitionCallback open  1')
            stream = mic.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True)
            print('RecognitionCallback open  2')
            self.openAudioSuccess = True
        except Exception as e:
            print(f'打开音频流失败: {e}')
            self.openAudioSuccess = False
    def on_close(self) -> None:
        if self.openAudioSuccess == False:
            return

        global mic
        global stream

        try:
            if stream:
                stream.stop_stream()
                stream.close()
                mic.terminate()
        except Exception as e:
            print(f'关闭音频流失败: {e}')
            self.openAudioSuccess = False
            return

        print('RecognitionCallback close')
        stream = None
        mic = None

    def on_event(self, result: RecognitionResult) -> None:
        data = result.get_sentence()
        if not data:
            return

        current_text = data.get("text", "")
        if not current_text:
            return

        # 实时输出：仅输出新增部分
        if data.get("end_time") is None:  # 中间结果
            new_part = current_text[len(self.last_text):]
            if new_part.strip():
                self.callback(new_part)
            self.last_text = current_text

        # 最终结果：句子结束
        elif data.get("end_time") is not None and not self.stop_flag:
            final_text = current_text[len(self.last_text):]
            if final_text.strip():
                self.callback(final_text)
            self.input_voice_message += current_text
            self.last_text = ""  # 清空缓存

    def set_callback(self, callback):
        self.callback = callback

class VoiceRecognition(QThread):
    VoiceRecognitionSignal = pyqtSignal(str)
    def __init__(self):
        super(VoiceRecognition, self).__init__()
        self.callback = VoiceCallback()
        self.callback.set_callback(self.voice_data_handle)
        self.stop_flag = False
        self.recognition = Recognition(
            model='paraformer-realtime-v1',
            format='pcm',
            sample_rate=16000,
            callback=self.callback,
            enable_intermediate_result=True,
            enable_punctuation_prediction=True,
            enable_inverse_text_normalization=True,
            buffer_size_in_seconds=1.0,  # 缓冲区时长，建议 0.8~1.5
        )

    def voice_data_handle(self, topic):
        self.VoiceRecognitionSignal.emit(topic)

    def run(self):
        global stream
        self.stop_flag = False
        self.callback.stop_flag = False
        try:
            self.recognition.start()
            print('self.recognition.start()')
            while True:
                if self.stop_flag:
                    try:
                        self.recognition.stop()
                        print('self.recognition.stop()')
                    except Exception as e:
                        print(f"尝试停止语音识别时发生错误：{e}")
                    break
                if stream:
                    try:
                        data = stream.read(3200, exception_on_overflow=False)
                    except IOError as e:
                        print(f"读取音频数据时发生错误: {e}")
                        continue  # 略过当前循环的剩余部分，直接进入下一次循环

                    try:
                        if data and len(data) > 0:
                            # print('Sending 3200 bytes to recognition engine.')
                            self.recognition.send_audio_frame(data)
                        else:
                            print("读取音频数据为空或不完整。")
                    except Exception as e:
                        print(f"发送音频数据到语音识别引擎时发生错误: {e}")
                        continue  # 略过当前循环的剩余部分，直接进入下一次循环
        except Exception as e:
            print(f"运行过程中遇到异常：{e}")
            return

        # finally:
        #     try:
        #         if self.stop_flag:
        #             print('Final stop of the recognition.')
        #             self.recognition.stop()   #导致崩溃的代码
        #     except Exception as e:
        #         print(f"尝试停止语音识别时发生错误：{e}")

    def stop_recognition(self):
        self.callback.stop_flag = True
        self.stop_flag = True
