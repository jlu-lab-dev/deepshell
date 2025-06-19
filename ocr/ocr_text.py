from paddleocr import PaddleOCR, draw_ocr
import re
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parents[1]))  # 上溯两级到项目根目录
from chat.assistant import Assistant
from ocr.ocr_yolo_detector import YOLODetector
import os

class OCRProcessor:
    def __init__(self, model_dir="ocr/paddle_models"):
        """
        参数说明：
        model_dir: 本地模型存储目录（需包含det/rec/cls子目录）
        """
        self.model_dir = model_dir

        # 本地模型路径配置
        self.ocr = PaddleOCR(
            use_angle_cls=True,
            lang="ch",
            det_model_dir=os.path.join(model_dir, "ch_PP-OCRv4_det_infer"),
            rec_model_dir=os.path.join(model_dir, "ch_PP-OCRv4_rec_infer"),
            cls_model_dir=os.path.join(model_dir, "ch_ppocr_mobile_v2.0_cls_infer")
        )

    def extract_text(self, img_path: str) -> str:
        """从图片中提取文字"""
        if not os.path.exists(img_path):
            raise FileNotFoundError(f"图片文件 {img_path} 不存在")

        result = self.ocr.ocr(img_path, cls=True)
        return " ".join([line[1][0] for line in result[0]])
    def generate_prompt(self, img_path: str, base_prompt: str = "解释这张图片") -> str:
        """
        生成图片解释提示词（默认包含OCR文本）

        参数:
            img_path: 图片路径
            base_prompt: 基础提示词模板，默认"解释这张图片"

        返回:
            包含OCR文本的完整提示词，格式："基础提示词（包含文字：[OCR文本]）"
        """
        try:
            # 获取OCR文本并去除首尾空白
            ocr_text = self.extract_text(img_path).strip()

            if ocr_text:
                # 包含文字时追加OCR内容
                return f"{base_prompt}（包含文字：{ocr_text}）"
            else:
                # 无文字时返回基础提示词
                return base_prompt

        except FileNotFoundError:
            # 文件不存在时仍返回基础提示词
            return base_prompt
        except Exception as e:
            # 其他异常时打印错误并返回基础提示词
            print(f"生成提示词时发生错误：{str(e)}")
            return base_prompt

# ================== 文本处理 ==================
class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """清洗OCR原始文本"""
        # 去除特殊字符
        text = re.sub(r'[?？*■□▢▣▤▥▦▧▨▩▪▫▬▭▮▯]', '', text)
        # 合并被分割的字段
        text = re.sub(r'(\w)\s+([：:])', r'\1\2', text)
        return text.strip()
    def ui_use_ocr(self , img_path: str)-> str:
        Q = OCRProcessor()
        raw_text = Q.extract_text(img_path)
        cleaned = self.clean_text(raw_text)
        #prompt = Q.generate_prompt(img_path)  # 预提示词
        print(cleaned)
        # 初始化检测器
        detector = YOLODetector(model_path="ocr/yolov10x.pt")

        # 执行检测
        detections = detector.predict(img_path, save=False)

        # 打印结果
        re = detector.print_detections()
        cleaned = "图片的文字信息如下：" + cleaned + "。图片的物体信息如下:" + re
        #cleaned = "图片的文字信息如下：" + cleaned + "。图片的物体信息如下:" + "暂未给出图片信息"
        return cleaned
    def send_to_ai(self , img_path: str)-> str:
        Q = OCRProcessor()
        raw_text = Q.extract_text(img_path)
        cleaned = self.clean_text(raw_text)
        prompt = Q.generate_prompt('result.jpg')  # 预提示词
        print(cleaned)
        # 初始化检测器
        detector = YOLODetector(model_path="yolov10x.pt")

        # 执行检测
        detections = detector.predict("result.png", save=True)

        # 打印结果
        re = detector.print_detections()
        cleaned = "我给你发送了一张图片，图片的文字信息如下：" + cleaned + "。图片的物体信息如下:" + "暂未给出图片信息" + "。请解析 "
        messages = [
            "我给你发送了一张图片，图片的文字信息如下：" + cleaned +
            "。图片的物体信息如下:" + re +
            "。请解析 "
        ]

        # print(raw_text)
        # print("清洗后文本:", cleaned + "...")
        assistant = Assistant("OCR")
        first_assistant = assistant.session_id
        print('massage', messages)
        response = assistant.chat(messages)
        # 将清洗文本发送给AI
        # result = ChatTalk.call_with_messages(cleaned)
        return response