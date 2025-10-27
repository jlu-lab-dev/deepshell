import sys
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QLineEdit, QFrame
)
from database.repository.knowledge_base_repository import KnowledgeBaseRepository


class CreateKnowledgeBaseWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setFixedSize(620, 256)
        self.initUI()
        self.kb_repo = KnowledgeBaseRepository()
        self._startPos = None
        self._isTracking = False

        self.setStyleSheet("""
                    QWidget {
                        background: #FFFFFF;
                        border-radius: 10px;
                    }
                """)

    def initUI(self):
        # 主布局（垂直排列标题栏和主体）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -----------------------------
        # 1. 标题栏
        # -----------------------------
        self.titleBar = QFrame()
        self.titleBar.setObjectName("TitleBar")
        self.titleBar.setFixedHeight(50)
        self.titleBar.setStyleSheet("""
                    QFrame#TitleBar {
                        background: transparent;
                        border-bottom: 1px solid #E0E0E0;
                    }
                """)

        # 标题内容
        self.titleLabel = QLabel("创建知识库")
        self.titleLabel.setStyleSheet("""
            QLabel {
                font-family: "Source Han Sans SC";
                font-weight: 400;
                font-size: 14px;
                color: #333333;
            }
        """)

        self.closeBtn = QPushButton()
        self.closeBtn.setIcon(QIcon("ui/icon/知识库/icon_知识库_创建知识库_关闭.png"))
        self.closeBtn.setFixedSize(13, 13)
        self.closeBtn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover { background-color: #F0F0F0; }
        """)
        self.closeBtn.clicked.connect(self.close)

        # 标题栏布局
        title_layout = QHBoxLayout(self.titleBar)
        title_layout.setContentsMargins(20, 0, 20, 0)
        title_layout.addWidget(self.titleLabel)
        title_layout.addStretch()
        title_layout.addWidget(self.closeBtn)

        # -----------------------------
        # 2. 主体区域
        # -----------------------------
        self.bodyFrame = QFrame()
        self.bodyFrame.setObjectName("BodyFrame")
        self.bodyFrame.setStyleSheet("""
                    QFrame#BodyFrame {
                        background: transparent;
                    }
                """)

        # 名称输入部分（保持原有样式）
        self.redStarLabel = QLabel("*")
        self.redStarLabel.setStyleSheet("color: red; font-size: 14px;")

        self.nameLabel = QLabel("名称")
        self.nameLabel.setStyleSheet("""
            QLabel {
                font-family: "Source Han Sans SC";
                font-weight: 400;
                font-size: 14px;
                color: #333333;
            }
        """)

        self.nameEdit = QLineEdit()
        self.nameEdit.setFixedSize(485, 36)
        self.nameEdit.setStyleSheet("""
            QLineEdit {
                background: #FAFAFA;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                padding: 4px 8px;
            }
            QLineEdit:focus { border-color: #66AFE9; }
        """)

        self.nameEdit.setPlaceholderText("请输入名称")

        # 按钮部分
        self.confirmBtn = QPushButton("确定")
        self.cancelBtn = QPushButton("取消")

        self.confirmBtn.setStyleSheet("""
            QPushButton {
                background: #007AFF;
                border: 1px solid #CCCCCC;
                border-radius: 8px;
                font-family: Microsoft YaHei;
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

        self.confirmBtn.clicked.connect(self.create_kb)

        self.cancelBtn.setStyleSheet("""
            QPushButton {
                background: #FAFAFA;
                border-radius: 8px;
                border: 1px solid #CCCCCC;
                font-family: Microsoft YaHei;
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

        for btn in [self.confirmBtn, self.cancelBtn]:
            btn.setFixedSize(104, 36)
        self.cancelBtn.clicked.connect(self.close)

        # -----------------------------
        # 布局结构调整（关键修改部分）
        # -----------------------------
        # 主布局添加标题栏和主体
        main_layout.addWidget(self.titleBar)
        main_layout.addWidget(self.bodyFrame)

        # 主体区域布局
        body_main_layout = QVBoxLayout(self.bodyFrame)
        body_main_layout.setContentsMargins(20, 42, 20, 42)
        body_main_layout.setSpacing(20)

        # 名称行布局
        name_layout = QHBoxLayout()
        name_layout.setSpacing(10)
        name_layout.addWidget(self.redStarLabel)
        name_layout.addWidget(self.nameLabel)
        name_layout.addWidget(self.nameEdit)
        name_layout.addStretch()

        # 按钮行布局
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.confirmBtn)
        btn_layout.setSpacing(10)
        btn_layout.addWidget(self.cancelBtn)

        # 组合主体布局
        body_main_layout.addLayout(name_layout)
        body_main_layout.addStretch()
        body_main_layout.addLayout(btn_layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._isTracking = True
            self._startPos = QPoint(event.globalPos() - self.pos())

    def mouseMoveEvent(self, event):
        if self._isTracking:
            self.move(event.globalPos() - self._startPos)

    def mouseReleaseEvent(self, event):
        self._isTracking = False

    def create_kb(self):
        kb_name = self.nameEdit.text().strip()

        if not kb_name:
            self.show_error("知识库名称不能为空")
            return

        # Create new knowledge base
        kb_data = {
            'name': kb_name,
            'description': 'This is a test knowledge base.',
            'embedding_model': 'test_model',
            'collection_name': 'test_collection',
            'persist_directory': '/path/to/directory',
            'chunk_size': 512,
            'chunk_overlap': 50
        }

        try:
            new_kb = self.kb_repo.create_knowledge_base(kb_data)
            if new_kb:
                self.show_success("创建成功")
                self.close()
                # 通知父窗口刷新
                if self.parent():
                    self.parent().refresh_kb_list()
            else:
                self.show_error("创建失败")
        except Exception as e:
            self.show_error(f"数据库错误: {str(e)}")

    def show_error(self, message):
        # 这里可以添加错误提示UI（比如红色文字提示）
        print(f"Error: {message}")  # 暂时用打印代替

    def show_success(self, message):
        # 这里可以添加成功提示UI
        print(f"Success: {message}")




def main():
    app = QApplication(sys.argv)
    window = CreateKnowledgeBaseWidget()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()