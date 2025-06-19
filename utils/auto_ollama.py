import subprocess
import sys
import platform

from PyQt5.QtCore import QThread, pyqtSignal

class OllamaTask(QThread):
    # 更新任务状态
    update_signal = pyqtSignal(str)

    def is_ollama_serving(self):
        """检查 Ollama 服务是否已在运行 (使用 pgrep)"""
        result = subprocess.run(['pgrep', '-f', 'ollama serve'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # 返回码为 0，则表示进程存在
        return result.returncode == 0

    def is_ollama_installed(self):
        try:
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def install_ollama(self):
        if self.is_ollama_installed():
            return

        system = platform.system()
        if system == "Darwin" or system == "Linux":
            # 安装 Ollama
            subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
        else:
            sys.exit(1)


    def pull_model(self, model_name="deepseek-r1:1.5b"):
        # 下载模型
        command = f"ollama pull {model_name}"
        subprocess.run(command, shell=True, check=True)

    def run_model(self, model_name="deepseek-r1:1.5b"):
        # 如果服务未运行，则启动服务
        if not self.is_ollama_serving():
            command = f"nohup ollama serve &"
            subprocess.run(command, shell=True, check=True)

    def run(self):
        try:
            # 运行模型
            self.update_signal.emit("Ollama 下载中...")
            self.install_ollama()
            self.update_signal.emit("DeepSeek-R1-1.5B 模型下载中...")
            self.pull_model()
            self.update_signal.emit("DeepSeek-R1-1.5B 已部署！")
            self.run_model()
        except Exception as e:
            print(f"OllamaTask exception: {e}")
            self.update_signal.emit("部署失败，请重试！")


if __name__ == "__main__":
    ollama_task = OllamaTask()
    # ollama_task.update_signal.connect(lambda msg: print(msg))
    # ollama_task.start()
    # ollama_task.wait()

