import os
import sys
import traceback
import subprocess
import whisper
import tempfile
import platform
import requests
import zipfile
import shutil


class AudioProcessor:
    def __init__(self, file_path):
        self.file_path = file_path
        pass

    def process(self) -> str:
        import os
        import sys
        import traceback
        import tempfile
        import platform
        import requests
        import zipfile
        import shutil
        
        try:
            # 确保ffmpeg可执行文件存在，但不会在代码中直接使用
            ffmpeg_path = self.find_ffmpeg()
            if not ffmpeg_path:
                print("未找到FFmpeg，尝试自动下载安装...")
                ffmpeg_path = self.ensure_ffmpeg_available()
                
            if not ffmpeg_path:
                return "错误：未找到可用的FFmpeg，且自动下载安装失败。请手动安装FFmpeg。"
                
            print(f"使用FFmpeg路径: {ffmpeg_path}")
            
            # 设置ffmpeg路径到环境变量，这样ffmpeg-python能找到它
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            current_path = os.environ.get('PATH', '')
            if ffmpeg_dir not in current_path:
                os.environ['PATH'] = f"{ffmpeg_dir}{os.pathsep}{current_path}"
                print(f"已将FFmpeg目录添加到PATH: {ffmpeg_dir}")
            
            # 尝试导入ffmpeg-python库
            try:
                import ffmpeg
                print("成功导入ffmpeg-python库")
            except ImportError:
                print("未找到ffmpeg-python库，尝试安装...")
                try:
                    import subprocess
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "ffmpeg-python"])
                    import ffmpeg
                    print("ffmpeg-python库安装成功")
                except Exception as e:
                    print(f"安装ffmpeg-python库失败: {str(e)}")
                    return f"错误：无法安装ffmpeg-python库 - {str(e)}"
            
            # 尝试导入whisper模块
            try:
                import whisper
            except ImportError:
                return "错误：未安装whisper模块，请先安装：pip install openai-whisper"
            
            # 检查文件是否存在
            print(f"尝试处理音频文件: {self.file_path}")
            if not os.path.exists(self.file_path):
                return f"错误：找不到音频文件: {self.file_path}"
            
            # 确定文件格式
            file_ext = os.path.splitext(self.file_path)[1].lower()[1:]
            print(f"文件扩展名: {file_ext}")
            
            # 支持的格式：wav, mp3, m4a, flac
            if file_ext not in ['wav', 'mp3', 'm4a', 'flac']:
                return f"错误：不支持的音频格式: {file_ext}。请使用 wav、mp3、m4a 或 flac 格式"
            
            # 创建临时工作目录
            temp_dir = tempfile.mkdtemp()
            print(f"创建临时目录: {temp_dir}")
            
            # 使用ffmpeg-python库转换为标准WAV格式
            temp_wav = os.path.join(temp_dir, "input_audio.wav")
            
            try:
                print(f"将音频转换为标准WAV格式: {temp_wav}")
                
                # 使用ffmpeg-python进行音频转换
                try:
                    # 使用纯粹的ffmpeg-python API
                    (
                        ffmpeg
                        .input(self.file_path)
                        .output(temp_wav, 
                                acodec='pcm_s16le',  # 线性PCM编码
                                ar=16000,            # 16kHz采样率
                                ac=1)                # 单声道
                        .overwrite_output()          # 覆盖已有文件
                        .run(quiet=True)             # 静默执行
                    )
                    print(f"使用ffmpeg-python转换成功: {temp_wav}")
                except Exception as e:
                    print(f"使用ffmpeg-python转换失败: {str(e)}")
                    return f"错误：音频转换失败 - {str(e)}"
                
                # 检查转换是否成功
                if not os.path.exists(temp_wav) or os.path.getsize(temp_wav) == 0:
                    return "错误：音频文件转换失败，输出文件为空"
                
                # 加载Whisper模型
                print("正在加载Whisper模型...")
                model = whisper.load_model("base")
                print("Whisper模型加载成功")
                
                # 执行识别
                try:
                    result = model.transcribe(temp_wav, language="zh", fp16=False)
                    
                    print(f"识别成功，结果长度: {len(result['text'])}")
                    
                    # 返回识别结果
                    return result['text']
                except Exception as e:
                    print(f"语音识别过程出错: {str(e)}")
                    traceback.print_exc()
                    return f"错误：语音识别失败 - {str(e)}"
                
            except Exception as e:
                print(f"转换或识别过程出错: {str(e)}")
                traceback.print_exc()
                return f"错误：无法识别音频文件 - {str(e)}"
            
            finally:
                # 清理临时文件
                try:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                        print(f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    print(f"清理临时文件时出错: {str(e)}")
                
        except Exception as e:
            print(f"音频处理过程中出错: {str(e)}")
            traceback.print_exc()
            return f"错误：转写失败 - {str(e)}"
    

            
    def find_ffmpeg(self):
        """查找系统中可用的FFmpeg路径"""
        import os
        import sys
        import subprocess
        
        try:
            # 首先检查环境变量中是否有ffmpeg
            if sys.platform == 'win32':
                try:
                    which_result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, check=False)
                    if which_result.returncode == 0:
                        # 返回第一个找到的路径
                        ffmpeg_path = which_result.stdout.strip().split('\n')[0]
                        print(f"系统PATH中找到FFmpeg: {ffmpeg_path}")
                        return ffmpeg_path
                except:
                    pass
            else:
                try:
                    which_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True, check=False)
                    if which_result.returncode == 0:
                        # 返回第一个找到的路径
                        ffmpeg_path = which_result.stdout.strip().split('\n')[0]
                        print(f"系统PATH中找到FFmpeg: {ffmpeg_path}")
                        return ffmpeg_path
                except:
                    pass
            
            # 尝试常见安装路径
            common_paths = []
            if sys.platform == 'win32':
                common_paths = [
                    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                    r"C:\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ffmpeg.exe"),
                    os.path.join(os.path.expanduser("~"), "ffmpeg", "bin", "ffmpeg.exe")
                ]
            else:
                common_paths = [
                    "/usr/bin/ffmpeg",
                    "/usr/local/bin/ffmpeg",
                    "/opt/ffmpeg/bin/ffmpeg",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ffmpeg")
                ]
            
            for path in common_paths:
                print(f"检查FFmpeg路径: {path}")
                if os.path.exists(path) and os.path.isfile(path):
                    print(f"在常见路径找到FFmpeg: {path}")
                    return path
            
            print("未找到FFmpeg，将尝试自动下载")
            return None
            
        except Exception as e:
            print(f"查找FFmpeg时出错: {str(e)}")
            return None
            
    def ensure_ffmpeg_available(self):
        """确保FFmpeg可用，如果不可用则自动下载安装"""
        import os
        import sys
        import platform
        import requests
        import zipfile
        import tempfile
        import shutil
        import subprocess
        
        # 1. 检查是否已经安装FFmpeg（再次检查，以防万一）
        try:
            result = subprocess.run(["ffmpeg", "-version"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if result.returncode == 0:
                print("FFmpeg已安装，无需下载")
                return "ffmpeg"
        except:
            pass

        # 2. 创建应用程序数据目录
        if sys.platform == "win32":
            app_data = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "AudioTranscription")
        else:
            app_data = os.path.join(os.path.expanduser("~"), ".AudioTranscription")

        os.makedirs(app_data, exist_ok=True)
        ffmpeg_dir = os.path.join(app_data, "ffmpeg")
        
        # 3. 检查应用程序目录中是否已经有FFmpeg
        if sys.platform == "win32":
            ffmpeg_exec = os.path.join(ffmpeg_dir, "ffmpeg.exe")
        else:
            ffmpeg_exec = os.path.join(ffmpeg_dir, "ffmpeg")
            
        if os.path.exists(ffmpeg_exec):
            print(f"使用已下载的FFmpeg: {ffmpeg_exec}")
            # 设置环境变量
            self.setup_ffmpeg_path(ffmpeg_dir)
            return ffmpeg_exec

        # 4. 下载并安装FFmpeg
        print("正在下载FFmpeg，请稍候...")
        try:
            # 获取对应系统的下载URL
            system = platform.system().lower()
            if system == "windows":
                url = "https://github.com/GyanD/codexffmpeg/releases/download/5.1.2/ffmpeg-5.1.2-essentials_build.zip"
            elif system == "darwin":  # macOS
                url = "https://evermeet.cx/ffmpeg/getrelease/zip"
            else:  # Linux
                url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"

            # 下载FFmpeg
            temp_zip = os.path.join(tempfile.gettempdir(), "ffmpeg_temp.zip")
            print(f"下载FFmpeg到临时文件: {temp_zip}")
            
            # 下载文件
            response = requests.get(url, stream=True)
            response.raise_for_status()

            with open(temp_zip, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # 创建目标目录
            os.makedirs(ffmpeg_dir, exist_ok=True)
            
            # 解压文件
            print(f"解压FFmpeg到: {ffmpeg_dir}")
            if temp_zip.endswith('.zip'):
                with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                    zip_ref.extractall(ffmpeg_dir)
            elif temp_zip.endswith('.tar.xz'):
                import tarfile
                with tarfile.open(temp_zip) as tar:
                    tar.extractall(path=ffmpeg_dir)
            
            # 处理可能的子目录情况
            self.fix_directory_structure(ffmpeg_dir)

            # 清理临时文件
            os.remove(temp_zip)

            # 设置环境变量
            self.setup_ffmpeg_path(ffmpeg_dir)

            print(f"FFmpeg已成功安装到: {ffmpeg_dir}")
            return ffmpeg_exec if os.path.exists(ffmpeg_exec) else None

        except Exception as e:
            print(f"安装FFmpeg时出错: {str(e)}")
            traceback.print_exc()
            return None

    def fix_directory_structure(self, directory):
        """修复解压后的目录结构，确保ffmpeg.exe在正确位置"""
        import os
        import shutil
        
        # 这个函数用来处理不同压缩包解压后的不同目录结构
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.startswith("ffmpeg") and (file.endswith(".exe") or "." not in file):
                    source_path = os.path.join(root, file)
                    target_path = os.path.join(directory, file)
                    if source_path != target_path:
                        print(f"移动ffmpeg从 {source_path} 到 {target_path}")
                        shutil.move(source_path, target_path)
                        if not file.endswith(".exe") and os.name == 'posix':
                            os.chmod(target_path, 0o755)  # 添加执行权限
                            
        # 在Windows上，确保文件名为ffmpeg.exe
        if os.name == 'nt':
            for file in os.listdir(directory):
                if file.startswith("ffmpeg") and file.endswith(".exe") and file != "ffmpeg.exe":
                    source_path = os.path.join(directory, file)
                    target_path = os.path.join(directory, "ffmpeg.exe")
                    print(f"重命名 {source_path} 为 {target_path}")
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    shutil.move(source_path, target_path)

    def setup_ffmpeg_path(self, ffmpeg_dir):
        """设置FFmpeg环境变量"""
        import os
        
        current_path = os.environ.get('PATH', '')
        if ffmpeg_dir not in current_path:
            os.environ['PATH'] = f"{ffmpeg_dir}{os.pathsep}{current_path}"
            print(f"已将FFmpeg目录添加到PATH: {ffmpeg_dir}")
        return ffmpeg_dir


# 测试函数
def test_ffmpeg_and_python_lib():
    """测试FFmpeg下载和ffmpeg-python库的可用性"""
    import os
    import sys
    import traceback
    
    print("=" * 50)
    print("开始测试FFmpeg和ffmpeg-python库")
    print("=" * 50)
    
    # 创建临时测试用的AudioProcessor实例git
    test_processor = AudioProcessor("test.mp3")
    
    # 1. 测试FFmpeg查找和下载
    print("\n1. 测试FFmpeg查找和下载:")
    try:
        ffmpeg_path = test_processor.find_ffmpeg()
        if ffmpeg_path:
            print(f"成功: 在系统中找到FFmpeg: {ffmpeg_path}")
        else:
            print("尝试自动下载FFmpeg...")
            ffmpeg_path = test_processor.ensure_ffmpeg_available()
            if ffmpeg_path:
                print(f"成功: 已下载并安装FFmpeg: {ffmpeg_path}")
            else:
                print("失败: 未能找到或下载FFmpeg")
    except Exception as e:
        print(f"错误: FFmpeg查找或下载失败 - {str(e)}")
        traceback.print_exc()
    
    # 2. 测试ffmpeg-python库
    print("\n2. 测试ffmpeg-python库:")
    try:
        try:
            import ffmpeg
            version = ffmpeg.__version__ if hasattr(ffmpeg, "__version__") else "未知版本"
            print(f"成功: ffmpeg-python库已安装，版本: {version}")
            
            # 检查基本功能是否可用
            try:
                stream = ffmpeg.input("test.mp3")
                print("成功: 可以创建ffmpeg输入流")
                
                output = ffmpeg.output(stream, "test.wav")
                print("成功: 可以创建ffmpeg输出流")
                
                command = ffmpeg.compile(output)
                print(f"成功: 可以编译ffmpeg命令: {' '.join(command)}")
                
                print("ffmpeg-python库功能测试通过")
            except Exception as e:
                print(f"错误: ffmpeg-python库功能测试失败 - {str(e)}")
        except ImportError:
            print("尝试安装ffmpeg-python库...")
            try:
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "ffmpeg-python"])
                import ffmpeg
                print("成功: ffmpeg-python库安装成功")
            except Exception as e:
                print(f"错误: ffmpeg-python库安装失败 - {str(e)}")
    except Exception as e:
        print(f"错误: ffmpeg-python库测试失败 - {str(e)}")
        traceback.print_exc()
    
    # 3. 测试环境变量
    print("\n3. 测试环境变量:")
    try:
        path = os.environ.get('PATH', '')
        print(f"PATH环境变量: {path}")
        
        if ffmpeg_path:
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            if ffmpeg_dir in path:
                print(f"成功: FFmpeg目录在PATH环境变量中: {ffmpeg_dir}")
            else:
                print(f"警告: FFmpeg目录不在PATH环境变量中: {ffmpeg_dir}")
    except Exception as e:
        print(f"错误: 环境变量测试失败 - {str(e)}")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)


# 如果直接运行此文件，则执行测试
if __name__ == "__main__":
    test_ffmpeg_and_python_lib()
