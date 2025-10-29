# auto_ollama.py

import subprocess
import sys
import platform
import os
from PyQt5.QtCore import QThread, pyqtSignal

class OllamaTask(QThread):
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(str)

    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.model_name = model_name

    def is_ollama_serving(self):
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ['tasklist'], check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding='utf-8', errors='ignore'
                )
                return 'ollama.exe' in result.stdout
            else:
                result = subprocess.run(['pgrep', '-f', 'ollama serve'], check=False, stdout=subprocess.DEVNULL)
                return result.returncode == 0
        except FileNotFoundError:
            return False
        except Exception as e:
            self.update_signal.emit(f"检查服务时出错: {e}")
            return False

    def is_ollama_installed(self):
        try:
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def install_ollama(self):
        if self.is_ollama_installed():
            self.update_signal.emit("Ollama 已安装。")
            return True
        self.update_signal.emit("正在尝试安装 Ollama...")
        system = platform.system()
        if system == "Darwin" or system == "Linux":
            try:
                command = "curl -fsSL https://ollama.com/install.sh | sh"
                subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                self.update_signal.emit("Ollama 安装成功！")
                return True
            except subprocess.CalledProcessError as e:
                self.update_signal.emit(f"Ollama 安装失败: {e.stderr}")
                return False
        elif system == "Windows":
            self.update_signal.emit("Windows系统需要手动安装。")
            self.update_signal.emit("请从 https://ollama.com 下载并运行安装程序。")
            self.update_signal.emit("安装完成后，请重新启动此程序。")
            try:
                os.startfile("https://ollama.com/download")
            except Exception:
                pass
            return False
        else:
            self.update_signal.emit(f"不支持的操作系统: {system}")
            return False

    def is_model_pulled(self):
        if not self.is_ollama_installed():
            return False
        try:
            self.update_signal.emit(f"正在检查模型: {self.model_name}...")
            result = subprocess.run(
                ["ollama", "list"], check=True, capture_output=True, text=True, encoding='utf-8'
            )
            return self.model_name in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def pull_model(self):
        self.update_signal.emit(f"开始下载模型: {self.model_name}...")
        try:
            command = ["ollama", "pull", self.model_name]
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1
            )
            for line in iter(process.stdout.readline, ''):
                self.progress_signal.emit(line.strip())
            process.stdout.close()
            return_code = process.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, command)
            return True
        except FileNotFoundError:
            self.update_signal.emit("错误: 'ollama' 命令未找到。")
            return False
        except Exception as e:
            self.update_signal.emit(f"下载模型时出错: {e}")
            return False

    def run_model_service(self):
        if self.is_ollama_serving():
            self.update_signal.emit("Ollama 服务已在运行。")
            return True
        self.update_signal.emit("正在启动 Ollama 服务...")
        try:
            if platform.system() == "Windows":
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                command = "nohup ollama serve > /dev/null 2>&1 &"
                subprocess.run(command, shell=True, check=True)
            self.sleep(3)
            if not self.is_ollama_serving():
                self.update_signal.emit("启动 Ollama 服务失败。")
                return False
            self.update_signal.emit("Ollama 服务已成功启动。")
            return True
        except Exception as e:
            self.update_signal.emit(f"启动服务时出错: {e}")
            return False

    def run(self):
        try:
            if not self.is_ollama_installed():
                if not self.install_ollama():
                    self.update_signal.emit("Ollama 安装未完成，部署中止。")
                    return
            if self.is_model_pulled():
                self.update_signal.emit(f"模型 {self.model_name} 已存在，无需下载。")
            else:
                if not self.pull_model():
                    self.update_signal.emit("模型下载失败，部署中止。")
                    return
            if not self.run_model_service():
                self.update_signal.emit("未能启动Ollama服务，部署中止。")
                return
            self.update_signal.emit(f"模型 {self.model_name} 已成功部署！")
        except Exception as e:
            self.update_signal.emit(f"部署失败: {e}")