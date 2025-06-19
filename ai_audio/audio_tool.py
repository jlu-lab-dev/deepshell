import whisper
import os
import sys
import subprocess
import ffmpeg
import traceback
import tempfile
from pathlib import Path
class AudioProcessor(object):
    def whisper_audio_to_text(self, audio_path, model="base"):
        file_ext = Path(audio_path).suffix.lower()
        if file_ext not in ['.wav', '.mp3']:
            ffmpeg_path = self.find_ffmpeg()
            if not ffmpeg_path:
                return "错误：未找到可用的FFmpeg，且自动下载安装失败。请手动安装FFmpeg。"
            ffmpeg_dir = os.path.dirname(ffmpeg_path)
            current_path = os.environ.get('PATH', '')
            if ffmpeg_dir not in current_path:
                os.environ['PATH'] = f"{ffmpeg_dir}{os.pathsep}{current_path}"
            if not os.path.exists(audio_path):
                return f"错误：找不到音频文件: {audio_path}"
                
            temp_dir = tempfile.mkdtemp()
            # 使用ffmpeg-python库转换为标准WAV格式
            temp_wav = os.path.join(temp_dir, "input_audio.wav")
                
            try:
                (
                    ffmpeg
                    .input(audio_path)
                    .output(temp_wav, 
                            acodec='pcm_s16le',  # 线性PCM编码
                            ar=16000,            # 16kHz采样率
                            ac=1)                # 单声道
                    .overwrite_output()          # 覆盖已有文件
                    .run(quiet=True)             # 静默执行
                )
            except Exception as e:
                return f"错误：音频转换失败 - {str(e)}"
            if not os.path.exists(temp_wav) or os.path.getsize(temp_wav) == 0:
                return "错误：音频文件转换失败，输出文件为空" 
            audio_path = temp_wav
        # 加载模型（首次运行会自动下载）
        model = whisper.load_model(model)  # 可选：tiny, base, small, medium, large
        print(f"开始转写音频文件: {audio_path}")
        result = model.transcribe(audio_path, language="zh")  # 中文
        return result["text"]

    def find_ffmpeg(self):
        """查找系统中可用的FFmpeg路径"""

        try:
            # 首先检查环境变量中是否有ffmpeg
            if sys.platform == 'win32':
                which_result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, check=False)
                if which_result.returncode == 0:
                    # 返回第一个找到的路径
                    ffmpeg_path = which_result.stdout.strip().split('\n')[0]
                    return ffmpeg_path
            else:
                which_result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True, check=False)
                if which_result.returncode == 0:
                    # 返回第一个找到的路径
                    ffmpeg_path = which_result.stdout.strip().split('\n')[0]
                    return ffmpeg_path
            # 尝试常见安装路径
            print("未找到FFmpeg")
            return None
            
        except Exception as e:
            print(f"查找FFmpeg时出错: {str(e)}")
            return None
