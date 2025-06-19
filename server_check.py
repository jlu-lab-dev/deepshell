import requests
import socket
from PyQt5.QtCore import QThread, pyqtSignal
import subprocess
import time


class ServerCheck(QThread):
    internet_change_signal = pyqtSignal(bool)

    def __init__(self):
        super(ServerCheck, self).__init__()
        self.internetStatus = False
        self.localserverStatus = False
        self.stop_flag = False

    def internet_status(self):
        return self.internetStatus

    def localserver_status(self):
        return self.localserverStatus

    def run(self):
        # print("loop_check")
        while not self.stop_flag:
            # print("loop_check...")
            status = self.is_connected_to_internet()
            if self.internetStatus != status:
                self.internetStatus = status
                self.internet_change_signal.emit(self.internetStatus)
            self.localserverStatus = self.get_ollama_server_status()
            time.sleep(1)

    def stop_check(self):
        self.stop_flag = True

    @staticmethod
    def is_connected_to_internet():
        try:
            # 你可以尝试连接任何知名的网站，这里使用Google
            response = requests.get('https://www.aliyun.com', timeout=1)
            # 如果请求成功，并且响应状态码为200，则认为连接到互联网
            if response.status_code == 200:
                return True
            else:
                return False
        except (requests.RequestException, socket.timeout):
            # 如果请求失败（包括超时），则认为没有连接到互联网
            return False

    @staticmethod
    def get_ollama_server_status():
        try:
            command_line = "ps -elf | grep 'ollama run qwen' | grep -v grep| wc -l"
            result = subprocess.run(command_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.stdout != "0":
                # print(result.stdout)
                # 你可以尝试连接任何知名的网站，这里使用Google
                response = requests.get('http://localhost:11434', timeout=5)
                # 如果请求成功，并且响应状态码为200，则认为连接到互联网
                if response.status_code == 200:
                    return True
                else:
                    return False
            else:
                print("ollama server is not running.")
                return False
        except (requests.RequestException, socket.timeout):
            # 如果请求失败（包括超时），则认为没有连接到互联网
            return False

