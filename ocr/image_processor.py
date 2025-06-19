import cv2
class ImageProcessor:
    def __init__(self):
        super().__init__()
    def enhance_contrast(self, img, method='CLAHE'):
        """对比度增强"""
        if method == 'CLAHE':
            # 转换为LAB颜色空间
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)

            # 应用CLAHE到L通道
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)

            # 合并通道并转回BGR
            limg = cv2.merge([cl, a, b])
            return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        else:
            # 直方图均衡化
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.equalizeHist(gray)

    def convert_grayscale(self, img):
        """转换为灰度图"""
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def denoise(self, img, method='nlm'):
        """去噪处理"""
        if method == 'nlm':
            # 非局部均值去噪
            return cv2.fastNlMeansDenoising(img, h=15, templateWindowSize=7, searchWindowSize=21)
        elif method == 'bilateral':
            # 双边滤波
            return cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)
        else:
            return img

    def process_pipeline(self, input_path, output_path):
        """完整处理流程"""
        # 读取原始图像
        img = cv2.imread(input_path)
        if img is None:
            print(f"错误：无法读取图像文件 {input_path}")
            return

        # 1. 增强对比度
        contrast_img = self.enhance_contrast(img)

        # 2. 转换为灰度图
        gray_img = self.convert_grayscale(contrast_img)

        # 3. 去噪处理
        denoised_img = self.denoise(gray_img)

        # 保存结果
        cv2.imwrite(output_path, denoised_img)
