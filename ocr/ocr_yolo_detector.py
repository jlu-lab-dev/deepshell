from ultralytics import YOLO
import os

class YOLODetector:
    def __init__(self, model_path="ocr/yolov10x.pt", conf_thres=0.25, iou_thres=0.7):
        """
        初始化YOLO目标检测器
        :param model_path: 模型文件路径（支持.pt或.yaml）
        :param conf_thres: 置信度阈值（0-1）
        :param iou_thres: IOU阈值（0-1）
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件 {model_path} 不存在")

        self.model = YOLO(model_path)
        self.conf_thres = conf_thres
        self.iou_thres = iou_thres
        self.results = None

    def predict(self, source, save=False, save_dir="runs/detect/predict"):
        """
        执行目标检测
        :param source: 输入源（文件路径/URL/PIL/numpy数组）
        :param save: 是否保存检测结果
        :param save_dir: 结果保存目录
        :return: 检测结果字典列表
        """
        self.results = self.model.predict(
            source=source,
            conf=self.conf_thres,
            iou=self.iou_thres,
            save=False
        )
        return self._format_results()

    def _format_results(self):
        """格式化检测结果为字典列表"""
        if not self.results:
            return []

        formatted = []
        for result in self.results:
            boxes = result.boxes.xyxy.tolist()
            classes = result.boxes.cls.tolist()
            confidences = result.boxes.conf.tolist()

            formatted.append({
                "image_path": result.path,
                "boxes": boxes,
                "classes": [result.names[int(cls)] for cls in classes],
                "confidences": confidences,
                "orig_img": result.orig_img
            })
        return formatted

    def show_result(self, index=0):
        """显示指定索引的检测结果"""
        if not self.results:
            print("请先执行predict()方法")
            return

        try:
            self.results[index].show()
        except IndexError:
            print(f"无效的结果索引 {index}")

    def print_detections(self, index=0, verbose=True):
        """
        返回检测结果的类别统计并打印详情（可选）

        参数:
            index: 结果索引（处理多张图片时使用）
            verbose: 是否打印详细信息

        返回:
            dict: 类别数量统计字典 {类别名称: 数量}
        """
        detections = self._format_results()
        if not detections:
            if verbose:
                print("未检测到任何目标")
            return {}

        try:
            result = detections[index]
        except IndexError:
            if verbose:
                print(f"无效的结果索引 {index}")
            return {}

        # 统计类别数量
        class_counts = {}
        for cls in result['classes']:
            class_counts[cls] = class_counts.get(cls, 0) + 1

        # 打印详细信息（可选）
        if verbose:
            print(f"\n检测结果：{result['image_path']}")
            print(f"共检测到 {sum(class_counts.values())} 个目标：")
            for cls, count in class_counts.items():
                print(f"- {cls}: {count} 个")
            for box, cls, conf in zip(result['boxes'],
                                      result['classes'],
                                      result['confidences']):
                print(f"  {cls}: 置信度 {conf:.2f}，坐标 {box}")
        class_counts=self.dict_to_text(class_counts)
        return class_counts

    def dict_to_text(self,result_dict):
        """将检测结果字典转换为自然语言描述"""
        if not result_dict:
            return "未检测到任何目标"

        items = []
        for obj, count in result_dict.items():
            if count == 1:
                items.append(f"1个{obj}")
            else:
                items.append(f"{count}个{obj}")

        if len(items) == 1:
            return f"检测到{items[0]}"
        else:
            return "检测到" + "、".join(items[:-1]) + f"和{items[-1]}"

    def get_annotated_image(self, index=0):
        """获取标注后的图像数组"""
        if not self.results:
            return None

        try:
            return self.results[index].plot()
        except IndexError:
            print(f"无效的结果索引 {index}")
            return None
