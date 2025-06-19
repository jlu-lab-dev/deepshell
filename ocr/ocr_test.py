import os
import sys
# 获取当前脚本的绝对路径
current_script_path = os.path.abspath(__file__)
# 计算项目根目录路径（根据实际层级调整）
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_script_path)))

# 添加项目根目录到 Python 路径
sys.path.append(project_root)


from ocr_text import OCRProcessor
from ocr_text import TextProcessor

from image_processor import ImageProcessor


if __name__ == '__main__':
    img_path='6.jpg'
    I=ImageProcessor()
    I.process_pipeline("6.jpg", 'result.png')#增强对比度，灰度化，去噪
    Q = OCRProcessor()
    prompt = Q.generate_prompt('result.png')  # 预提示词
    #print("预提示词：",prompt)
    T=TextProcessor()
    result=T.send_to_ai(img_path)#AI识别图片的结果
    print(result)