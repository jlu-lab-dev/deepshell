
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QFrame


class ConfigurationPage(QWidget):
    def __init__(self, current_kb=None):
        super().__init__()
        self.current_kb = current_kb
        self.init_ui()

    def init_ui(self):
        self.setFixedSize(959, 607)
        self.setAttribute(Qt.WA_StyledBackground)
        self.setStyleSheet("""
            background: #FFFFFF;
            border-radius: 8px;
            border: 1px solid #E6E6E6;
        """)

        # 顶部
        top_widget = self.init_top_pane()

        # 横线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setLineWidth(1)
        line.setStyleSheet("""
            width: 917px;
            height: 1px;
            background: #E5E5E5;
            border-radius: 1px;
        """)

        # 中间和底部滚动区域
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet("""
            border: None;
        """)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_area_content = QWidget()
        scroll_area_content.setStyleSheet("""
            border: None;
        """)

        # 中间
        middle_left_widget = self.init_middle_left_pane()
        middle_right_widget = self.init_middle_right_pane()
        middle_layout = QHBoxLayout()
        middle_layout.addWidget(middle_left_widget)
        middle_layout.addWidget(middle_right_widget)

        # 底部按钮
        bottom_widget = self.init_bottom_pane()

        # 中间和底部滚动区域布局
        content_layout = QVBoxLayout()
        content_layout.addLayout(middle_layout)
        content_layout.addWidget(bottom_widget)

        scroll_area_content.setLayout(content_layout)
        scroll_area.setWidget(scroll_area_content)

        # 整体布局
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 18, 18, 24)
        layout.setSpacing(0)
        layout.addWidget(top_widget)
        layout.addWidget(line)
        layout.addWidget(scroll_area)
        self.setLayout(layout)
        self.adjustSize()

    def init_top_pane(self):
        top_widget = QWidget()
        top_widget.setStyleSheet("""
            border: None;
        """)

        config_label = QLabel("配置")
        config_label.setStyleSheet("""
            width: 35px;
            height: 17px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 18px;
            color: #333333;
            border: None;
        """)

        info_label = QLabel("在这里更新您的知识库详细信息，尤其是解析方法。")
        info_label.setStyleSheet("""
            width: 314px;
            height: 15px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #999999;
            border: None;
        """)

        top_layout = QVBoxLayout()
        top_layout.addWidget(config_label)
        top_layout.addWidget(info_label)

        top_widget.setLayout(top_layout)
        return top_widget

    def init_middle_left_pane(self):
        middle_left_widget = QWidget()
        middle_left_widget.setFixedWidth(458)
        middle_left_widget.setStyleSheet("""
            border: None;
        """)

        # 知识库名称
        red_star_label = QLabel("*")
        red_star_label.setStyleSheet("color: red; font-size: 14px; border: None;")
        kb_name_label = QLabel("知识库名称")
        kb_name_label.setStyleSheet("""
            width: 70px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            border: None;
        """)
        kb_name_layout = QHBoxLayout()
        kb_name_layout.addWidget(red_star_label)
        kb_name_layout.addWidget(kb_name_label)
        kb_name_layout.addStretch()

        # 知识库图片
        kb_img_label = QLabel("知识库图片")
        kb_img_label.setStyleSheet("""
            width: 70px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            border: None;
        """)

        middle_left_layout = QVBoxLayout()
        middle_left_layout.addLayout(kb_name_layout)
        middle_left_layout.addWidget(kb_img_label)

        middle_left_widget.setLayout(middle_left_layout)
        return middle_left_widget

    def init_middle_right_pane(self):
        middle_right_widget = QWidget()
        middle_right_widget.setFixedWidth(458)
        middle_right_widget.setStyleSheet("""
            border: None;
        """)

        # “General” 分块方法说明
        chunk_info_title_label = QLabel('"General" 分块方法说明')
        chunk_info_title_label.setStyleSheet("""
            width: 85px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: bold;
            font-size: 18px;
            color: #333333;
            border: None;
            alignment: left;
        """)

        chunk_info_content_label = QLabel(
            "支持的文件格式为DOCX、EXCEL、PDF、TXT、MD、JSON、JPG、XML。\n\n"
            + "此方法将简单的方法应用于块文件：\n\n"
            + "● 系统将使用视觉检测模型将连续文本分割成多个片段。\n"
            + "● 接下来，这些连续的片段被合并成Token数不超过“Token数”的块。\n\n")
        chunk_info_content_label.setWordWrap(True)
        chunk_info_content_label.setStyleSheet("""
            width: 472px;
            height: 150px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            border: None;
            alignment: left;
        """)

        # “General” 示例
        example_title_label = QLabel('"General" 示例')
        example_title_label.setStyleSheet("""
            width: 188px;
            height: 39px;
            font-family: Source Han Sans SC;
            font-weight: bold;
            font-size: 18px;
            color: #333333;
            border: None;
            alignment: left;
        """)
        example_content_label = QLabel("提出以下屏幕截图以促进理解。")

        example_content_label.setStyleSheet("""
            width: 188px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            border: None;
            alignment: left;
        """)

        middle_right_layout = QVBoxLayout()
        middle_right_layout.addWidget(chunk_info_title_label)
        middle_right_layout.addWidget(chunk_info_content_label)
        middle_right_layout.addWidget(example_title_label)
        middle_right_layout.addWidget(example_content_label)

        middle_right_widget.setLayout(middle_right_layout)
        return middle_right_widget

    def init_bottom_pane(self):
        bottom_widget = QWidget()
        bottom_widget.setStyleSheet("""
            border: None;
        """)

        save_btn = QPushButton("保存")
        save_btn.setStyleSheet("""
            QPushButton {
                width: 104px;
                height: 36px;
                background: #007AFF;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                font-family: Source Han Sans SC;
                font-weight: 400;
                font-size: 16px;
                color: #FFFFFF;
            }
            QPushButton:hover { 
                background: #0066CC;
                border-color: #0052A3;
            }
            QPushButton:pressed { 
                background: #0052A3;
            }
        """)

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                width: 104px;
                height: 36px;
                background: #FAFAFA;
                border-radius: 8px;
                border: 1px solid #CCCCCC;
                font-family: Source Han Sans SC;
                font-weight: 400;
                font-size: 16px;
                color: #333333;
            }
            QPushButton:hover { 
                background: #F3F3F3;
                border-color: #B3B3B3;  /* 加深边框颜色 */
            }
            QPushButton:pressed { 
                background: #E0E0E0;  /* 新增按压效果 */
                border-color: #999999;
            }
        """)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(save_btn)
        bottom_layout.addWidget(cancel_btn)
        bottom_layout.addStretch()

        bottom_widget.setLayout(bottom_layout)
        return bottom_widget

