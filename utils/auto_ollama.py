import subprocess
import sys
import platform
import os

from PyQt5.QtCore import QThread, pyqtSignal


class OllamaTask(QThread):
    # 用于更新主要任务状态，例如 "开始下载" 或 "部署完成"
    update_signal = pyqtSignal(str)
    # 用于流式传输下载进度行的信号
    progress_signal = pyqtSignal(str)

    def is_ollama_serving(self):
        """检查 Ollama 服务是否已在运行"""
        try:
            if platform.system() == "Windows":
                # 在Windows上，使用tasklist检查ollama.exe进程
                result = subprocess.run(
                    ['tasklist'],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding='utf-8',
                    errors='ignore'
                )
                return 'ollama.exe' in result.stdout
            else:
                # 在Linux/macOS上，使用pgrep
                result = subprocess.run(['pgrep', '-f', 'ollama serve'], check=False, stdout=subprocess.DEVNULL)
                return result.returncode == 0
        except FileNotFoundError:
            return False
        except Exception as e:
            self.update_signal.emit(f"检查服务时出错: {e}")
            return False

    def is_ollama_installed(self):
        """检查Ollama CLI是否在系统的PATH中"""
        try:
            # 将输出重定向到DEVNULL以保持静默
            subprocess.run(["ollama", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def install_ollama(self):
        """根据操作系统尝试安装Ollama"""
        if self.is_ollama_installed():
            self.update_signal.emit("Ollama 已安装。")
            return True

        self.update_signal.emit("正在尝试安装 Ollama...")
        system = platform.system()
        if system == "Darwin" or system == "Linux":
            try:
                # 在Linux和macOS上运行安装脚本
                command = "curl -fsSL https://ollama.com/install.sh | sh"
                process = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                self.update_signal.emit("Ollama 安装成功！")
                # 安装后需要重新检查，因为可能需要新的shell会话
                return True
            except subprocess.CalledProcessError as e:
                self.update_signal.emit(f"Ollama 安装失败: {e.stderr}")
                return False
        elif system == "Windows":
            # 对于Windows，指导用户手动安装
            self.update_signal.emit("Windows系统需要手动安装。")
            self.update_signal.emit("请从 https://ollama.com 下载并运行安装程序。")
            self.update_signal.emit("安装完成后，请重新启动此程序。")
            # 自动打开下载页面
            try:
                os.startfile("https://ollama.com/download")
            except Exception:
                pass  # 如果失败也无妨
            return False
        else:
            self.update_signal.emit(f"不支持的操作系统: {system}")
            return False

    def is_model_pulled(self, model_name="deepseek-r1:1.5b"):
        """检查指定的模型是否已经被拉取"""
        if not self.is_ollama_installed():
            return False
        try:
            self.update_signal.emit(f"正在检查模型: {model_name}...")
            result = subprocess.run(
                ["ollama", "list"],
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            # 检查输出中是否包含模型名称
            return model_name in result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            # 如果ollama list命令失败，则假定模型不存在
            return False

    def pull_model(self, model_name="deepseek-r1:1.5b"):
        """使用Popen实时流式传输输出来拉取模型"""
        self.update_signal.emit(f"开始下载模型: {model_name}...")
        try:
            command = ["ollama", "pull", model_name]
            # 使用Popen来异步执行命令并捕获输出
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将stderr重定向到stdout
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1  # 行缓冲
            )

            # 逐行读取输出并发送信号
            for line in iter(process.stdout.readline, ''):
                self.progress_signal.emit(line.strip())

            process.stdout.close()
            return_code = process.wait()

            if return_code != 0:
                raise subprocess.CalledProcessError(return_code, command)

            return True
        except FileNotFoundError:
            self.update_signal.emit("错误: 'ollama' 命令未找到。请确保它已安装并位于您的PATH中。")
            return False
        except Exception as e:
            self.update_signal.emit(f"下载模型时出错: {e}")
            return False

    def run_model_service(self):
        """在后台启动Ollama服务"""
        if self.is_ollama_serving():
            self.update_signal.emit("Ollama 服务已在运行。")
            return True

        self.update_signal.emit("正在启动 Ollama 服务...")
        try:
            if platform.system() == "Windows":
                # 在Windows上，Ollama通常作为后台服务在安装时设置好。
                # 如果没有运行，可以尝试启动它（需要管理员权限）。
                # 这里我们假设安装程序正确设置了服务。
                self.update_signal.emit("请确保 Ollama 服务正在运行。")
                # 简单的启动方法（可能需要管理员权限）
                subprocess.Popen(["ollama", "serve"], creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # 在Linux/macOS上，使用nohup在后台启动
                command = "nohup ollama serve > /dev/null 2>&1 &"
                subprocess.run(command, shell=True, check=True)

            # 等待一小会儿让服务启动
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
        """执行完整的部署流程"""
        try:
            model_to_deploy = "deepseek-r1:1.5b"  # 定义要部署的模型

            # 1. 检查/安装 Ollama
            if not self.is_ollama_installed():
                if not self.install_ollama():
                    # 在Windows上，会指导用户手动安装并返回False
                    self.update_signal.emit("Ollama 安装未完成，部署中止。")
                    return

            # 2. 检查模型是否存在
            if self.is_model_pulled(model_to_deploy):
                self.update_signal.emit(f"模型 {model_to_deploy} 已存在，无需下载。")
            else:
                # 3. 如果不存在，则下载模型
                if not self.pull_model(model_to_deploy):
                    self.update_signal.emit("模型下载失败，部署中止。")
                    return

            # 4. 启动Ollama服务
            if not self.run_model_service():
                self.update_signal.emit("未能启动Ollama服务，部署中止。")
                return

            self.update_signal.emit(f"模型 {model_to_deploy} 已成功部署！")

        except Exception as e:
            self.update_signal.emit(f"部署失败: {e}")