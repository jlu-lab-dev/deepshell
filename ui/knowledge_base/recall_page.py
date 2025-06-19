from PyQt5.QtCore import QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout, QFrame, QPushButton, QTextEdit

from ui.knowledge_base.draggable_divider import DraggableDivider


class RecallPage(QWidget):
    def __init__(self, current_kb=None):
        super().__init__()
        self.current_kb = current_kb
        self.init_ui()

    def init_ui(self):
        # 左边
        left_widget = self.init_left_pane()

        # 右边
        right_widget = self.init_right_pane()

        # 整体布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(left_widget)
        layout.addSpacing(24)
        layout.addWidget(right_widget)
        self.setFixedSize(959, 607)

    def init_left_pane(self):
        left_widget = QWidget()
        left_widget.setFixedSize(340, 607)
        left_widget.setStyleSheet("""
                    background: #FFFFFF;
                    border-radius: 8px;
                    border: 1px solid #E6E6E6;
                """)

        # 左边内容
        recall_test_label = QLabel("召回测试")
        recall_test_label.setStyleSheet("""
                    width: 150px;
                    height: 18px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 18px;
                    color: #333333;
                    border: none;
                """)
        hint_label = QLabel("最后一步！成功后，剩下的就交给 AI 吧。")
        hint_label.setStyleSheet("""
                    width: 140px;
                    height: 14px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 14px;
                    color: #999999;
                    border: none;
                """)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setLineWidth(1)
        line.setStyleSheet("""
                    width: 298px;
                    height: 1px;
                    background: #E5E5E5;
                    border-radius: 1px;
                """)

        # 相似度阈值
        sim_threshold_label = QLabel("相似度阈值")
        sim_threshold_label.setStyleSheet("""
                    width: 248px;
                    height: 15px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 14px;
                    color: #333333;
                    border: none;
                """)
        sim_threshold_tip_btn = QPushButton()
        sim_threshold_tip_btn.setStyleSheet("""
                    width: 16px;
                    height: 16px;
                    border: none;
                """)
        sim_threshold_tip_btn.setIcon(QIcon("ui/icon/知识库/icon_召回测试_说明.png"))
        sim_threshold_tip_btn.clicked.connect(self.sim_threshold_tip)

        sim_threshold_layout = QHBoxLayout()
        sim_threshold_layout.addWidget(sim_threshold_label)
        sim_threshold_layout.addWidget(sim_threshold_tip_btn)
        sim_threshold_layout.addStretch()

        sim_threshold_divider = DraggableDivider()

        # 关键字相似度权重
        keyword_sim_weight_label = QLabel("关键字相似度权重")
        keyword_sim_weight_label.setStyleSheet("""
                    width: 112px;
                    height: 14px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 14px;
                    color: #333333;
                    border: none;
                """)
        keyword_sim_weight_tip_btn = QPushButton()
        sim_threshold_tip_btn.setStyleSheet("""
                    width: 16px;
                    height: 16px;
                    border: none;
                """)
        keyword_sim_weight_tip_btn.setIcon(QIcon("ui/icon/知识库/icon_召回测试_说明.png"))
        keyword_sim_weight_tip_btn.clicked.connect(self.keyword_sim_weight_tip)

        keyword_sim_weight_layout = QHBoxLayout()
        keyword_sim_weight_layout.addWidget(keyword_sim_weight_label)
        keyword_sim_weight_layout.addWidget(keyword_sim_weight_tip_btn)
        keyword_sim_weight_layout.addStretch()

        keyword_sim_weight_divider = DraggableDivider()

        # Rerank模型
        rerank_label = QLabel("Rerank模型")
        rerank_label.setStyleSheet("""
                            width: 112px;
                            height: 14px;
                            font-family: Source Han Sans SC;
                            font-weight: 400;
                            font-size: 14px;
                            color: #333333;
                            border: none;
                        """)
        rerank_tip_btn = QPushButton()
        rerank_tip_btn.setStyleSheet("""
                            width: 16px;
                            height: 16px;
                            border: none;
                        """)
        rerank_tip_btn.setIcon(QIcon("ui/icon/知识库/icon_召回测试_说明.png"))
        rerank_tip_btn.clicked.connect(self.rerank_tip)

        rerank_layout = QHBoxLayout()
        rerank_layout.addWidget(rerank_label)
        rerank_layout.addWidget(rerank_tip_btn)
        rerank_layout.addStretch()

        rerank_model_select_btn = QPushButton("请选择")
        rerank_model_select_btn.setStyleSheet("""
                    width: 112px;
                    height: 20px;
                    background: #FAFAFA;
                    border-radius: 8px;
                    border: 1px solid #CCCCCC;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 16px;
                    color: #333333;
                """)

        # 测试文本
        test_label = QLabel("测试文本")
        test_label.setStyleSheet("""
                    width: 56px;
                    height: 14px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 14px;
                    color: #333333;
                    border: none;
                """)

        test_text_edit = QTextEdit()
        test_text_edit.setStyleSheet("""
                    width: 292px;
                    height: 185px;
                    background: #FAFAFA;
                    border-radius: 5px;
                    border: 1px solid #CCCCCC;
                """)

        test_btn = QPushButton("测试")
        test_btn.setStyleSheet("""
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
                """)
        test_btn_layout = QHBoxLayout()
        test_btn_layout.addStretch()
        test_btn_layout.addWidget(test_btn)

        # 整体布局
        left_widget_layout = QVBoxLayout()
        left_widget_layout.setContentsMargins(24, 18, 18, 24)
        left_widget_layout.addWidget(recall_test_label)
        left_widget_layout.addSpacing(17)
        left_widget_layout.addWidget(hint_label)
        left_widget_layout.addSpacing(17)
        left_widget_layout.addWidget(line)
        left_widget_layout.addSpacing(23)
        left_widget_layout.addLayout(sim_threshold_layout)
        left_widget_layout.addSpacing(4)
        left_widget_layout.addWidget(sim_threshold_divider)
        left_widget_layout.addSpacing(34)
        left_widget_layout.addLayout(keyword_sim_weight_layout)
        left_widget_layout.addSpacing(13)
        left_widget_layout.addWidget(keyword_sim_weight_divider)
        left_widget_layout.addSpacing(29)
        left_widget_layout.addLayout(rerank_layout)
        left_widget_layout.addSpacing(4)
        left_widget_layout.addWidget(rerank_model_select_btn)
        left_widget_layout.addSpacing(30)
        left_widget_layout.addWidget(test_label)
        left_widget_layout.addSpacing(7)
        left_widget_layout.addWidget(test_text_edit)
        left_widget_layout.addSpacing(17)
        left_widget_layout.addLayout(test_btn_layout)
        left_widget.setLayout(left_widget_layout)

        return left_widget

    def init_right_pane(self):
        right_widget = QWidget()
        right_widget.setFixedSize(595, 607)
        right_widget.setStyleSheet("""
                    background: #FFFFFF;
                    border-radius: 8px;
                    border: 1px solid #E6E6E6;
                """)

        # 显示选定文件
        fold_button = QPushButton()
        fold_button.setStyleSheet("""
            width: 16px;
            height: 16px;
            background: #FAFAFA;
        """)
        fold_button.setIcon(QIcon("ui/icon/知识库/icon_召回测试_文件列表_收起.png"))
        fold_button.setIconSize(QSize(14, 14))

        selected_file_label = QLabel("0/0 选定的文件")
        selected_file_label.setStyleSheet("""
            width: 78px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            border: None;
        """)

        selected_file_text_layout = QHBoxLayout()
        selected_file_text_layout.addWidget(fold_button)
        selected_file_text_layout.addWidget(selected_file_label)
        selected_file_text_layout.addStretch()

        # 翻页按钮
        total_page_label = QLabel("总共4条")
        total_page_label.setStyleSheet("""
            width: 56px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            border: None;
        """)

        left_page_btn = QPushButton()
        left_page_btn.setStyleSheet("""
            width: 16px;
            height: 16px;
            background: rgba(51,51,51,0);
        """)
        left_page_btn.setIcon(QIcon(QPixmap("ui/icon/知识库/icon_翻页_左.png").scaled(7, 13)))
        left_page_btn.clicked.connect(self.left_page_clicked)

        page_btn_layout = self.create_pages_btn()

        right_page_btn = QPushButton()
        right_page_btn.setStyleSheet("""
            width: 16px;
            height: 16px;
            background: rgba(51,51,51,0);
        """)
        right_page_btn.setIcon(QIcon(QPixmap("ui/icon/知识库/icon_翻页_右.png").scaled(7, 13)))
        right_page_btn.clicked.connect(self.right_page_clicked)

        show_page_num_btn = QPushButton("10条/页")
        show_page_num_btn.setStyleSheet("""
            width: 96px;
            height: 24px;
            background: #FFFFFF;
            border-radius: 4px;
            border: 1px solid #CCCCCC;
            border: None;
        """)

        page_layout = QHBoxLayout()
        page_layout.addStretch()
        page_layout.addWidget(total_page_label)
        page_layout.addSpacing(11)
        page_layout.addWidget(left_page_btn)
        page_layout.addSpacing(12)
        page_layout.addLayout(page_btn_layout)
        page_layout.addSpacing(12)
        page_layout.addWidget(right_page_btn)
        page_layout.addSpacing(12)
        page_layout.addWidget(show_page_num_btn)

        right_widget_layout = QVBoxLayout()
        right_widget_layout.setContentsMargins(24, 18, 18, 24)
        right_widget_layout.addLayout(selected_file_text_layout)
        right_widget_layout.addStretch()
        right_widget_layout.addLayout(page_layout)

        right_widget.setLayout(right_widget_layout)
        return right_widget

    def create_pages_btn(self):
        pass

    def sim_threshold_tip(self):
        pass

    def keyword_sim_weight_tip(self):
        pass

    def rerank_tip(self):
        pass

    def left_page_clicked(self):
        pass

    def right_page_clicked(self):
        pass