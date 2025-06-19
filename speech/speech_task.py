# coding=utf-8
#
# Installation instructions for pyaudio:
# APPLE Mac OS X
#   brew install portaudio 
#   pip install pyaudio
# Debian/Ubuntu
#   sudo apt-get install python-pyaudio python3-pyaudio
#   or
#   pip install pyaudio
# CentOS
#   sudo yum install -y portaudio portaudio-devel && pip install pyaudio
# Microsoft Windows
#   python -m pip install pyaudio

import dashscope
import pyaudio

from PyQt5.QtCore import QThread, pyqtSignal
from dashscope.api_entities.dashscope_response import SpeechSynthesisResponse
from dashscope.audio.tts import ResultCallback, SpeechSynthesizer, SpeechSynthesisResult

dashscope.api_key = 'sk-sGI5D8mkwW'


class Callback(ResultCallback):
    _player = None
    _stream = None
    _stop_flag = False
    _first_flag = True
    _callback = None

    def set_callback(self, callback):
        self._callback = callback

    def stop_play(self):
        print("stop_play")
        if self._stream:
            self._stop_flag = True
            self._first_flag = True
        # self._stream.stop_stream()
        # self._stream.close()

    def on_open(self):
        print('Speech synthesizer is opened.')
        self._player = pyaudio.PyAudio()
        self._stream = self._player.open(
            format=pyaudio.paInt16,
            channels=1, 
            rate=48000,
            output=True)

    def on_complete(self):
        self._stop_flag = False
        self._first_flag = False
        self._callback()
        print('Speech synthesizer is completed.')

    def on_error(self, response: SpeechSynthesisResponse):
        print('Speech synthesizer failed, response is %s' % (str(response)))

    def on_close(self):
        print('Speech synthesizer is closed.')
        self._stream.stop_stream()
        self._stream.close()
        self._player.terminate()

    def on_event(self, result: SpeechSynthesisResult):
        if self._stop_flag:
            if self._first_flag:
                self.on_close()
                self._first_flag = False
            return

        if result.get_audio_frame() is not None:
            # print('audio result length:', sys.getsizeof(result.get_audio_frame()))
            try:
                self._stream.write(result.get_audio_frame())
            except Exception as e:
                print(f"写音频流时异常: {e}")

        if result.get_timestamp() is not None:
            print('timestamp result:', str(result.get_timestamp()))


class Speech:
    callback = None
    complete_callback = None

    def __init__(self):
        self.callback = Callback()
        self.callback.set_callback(self.complete_callback_handle)

    def complete_callback_handle(self):
        print("complete_callback_handle")
        self.complete_callback()

    def set_callback(self, callback):
        self.complete_callback = callback

    def text_play(self, message):
        try:
            SpeechSynthesizer.call(model='sambert-zhiru-v1',
                                   text=message,
                                   sample_rate=48000,
                                   format='pcm',
                                   callback=self.callback)
        except Exception as e:
            print(f"text_play输出音频流时异常: {e}")

    def stop_play(self):
        if self.callback:
              self.callback.stop_play()

    @staticmethod
    def short_text_play(message):
        callback = Callback()
        try:
            SpeechSynthesizer.call(model='sambert-zhiru-v1',
                                   text=message,
                                   sample_rate=48000,
                                   format='pcm',
                                   callback=callback)
        except Exception as e:
            print(f"short_text_play输出音频流时异常: {e}")


class SpeechTask(QThread):
    complete_signal = pyqtSignal(str)
    message = ""
    speech = None
    callback = None
    bubble_message = None

    def __init__(self):
        super(SpeechTask, self).__init__()
        self.topic = ""
        self.speech = Speech()

    def speech_callback_handle(self):
        print("callback_handle")
        if self.bubble_message:
            self.callback(self.bubble_message)

    def set_message(self, message, bubble_message=None):
        self.message = message
        self.bubble_message = bubble_message

    def set_callback(self, callback):
        self.callback = callback

    def stop_speech(self):
        print("stop_speech")
        self.speech.stop_play()

    def run(self):
        try:
            self.speech.set_callback(self.speech_callback_handle)
            self.speech.text_play(self.message)
        except Exception as e:
            print(f"合成音频输出任务异常: {e}")

