import sys

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLabel,
    QAction, QMenu, QFrame
)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QSize, QPoint

from ui.knowledge_base.configuration_page import ConfigurationPage
from ui.knowledge_base.dataset_page import DatasetPage
from config.config_manager import ConfigManager

from database.repository.knowledge_base_repository import KnowledgeBaseRepository
from ui.knowledge_base.recall_page import RecallPage


class EnterKnowledgeBase(QWidget):
    def __init__(self,kb = None,parent = None):
        super().__init__(parent)
        self.current_kb = kb
        self.repository = KnowledgeBaseRepository()
        self.current_kb_name = kb.name
        self.parent_window = parent
        self.knowledge_bases = None
        self.current_page_index = 0
        self.initUI()
        self.center_on_screen()
        self.load_documents()  # 加载kb中文件

    def load_documents(self):
        """加载知识库的文档"""
        if self.current_kb and self.current_kb.id:
            documents = self.repository.get_documents_by_kb(self.current_kb.id)
            self.dataset_page.load_files(documents)

    def switch_page(self, index):
        self.current_page_index = index
        self.stackedWidget.setCurrentIndex(index)
        pages = ["数据集", "召回测试", "配置"]

        # 使用内联样式代替CSS类
        self.pathLabel.setText(
            f'<a href="#" style="color:#999999; text-decoration:none;">知识库</a>'
            f'<span style="color:#999999; margin:0 4px;">/</span>'
            f'<span style="color:#333333;">{pages[index]}</span>'
        )

    def initUI(self):
        # ============ 主部件整体设置 ============
        self.setFixedSize(1250, 750)
        self.setStyleSheet("background: #F5F5F5;")
        self.setWindowTitle(f"{ConfigManager().app_config['name']} - 知识库")
        self.setWindowIcon(QIcon("ui/icon/DeepShell/shell.png"))

        # 整体布局
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        # ============ 顶部导航栏 ============
        topWidget = QWidget()
        topWidget.setFixedSize(1250, 45)
        topWidget.setStyleSheet("""
            background: #FFFFFF;
            border-bottom: 1px solid #E6E6E6;
        """)
        topLayout = QHBoxLayout(topWidget)
        topLayout.setContentsMargins(20, 0, 20, 0)

        # 路径显示
        self.pathLabel = QLabel()
        self.pathLabel.setText(
            f'<a href="#" style="color:#999999; text-decoration:none;">知识库</a>'
            f'<span style="color:#999999; margin:0 4px;">/</span>'
            f'<span style="color:#333333;">数据集</span>'
        )
        self.pathLabel.setTextFormat(Qt.RichText)
        self.pathLabel.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.pathLabel.linkActivated.connect(self.on_nav_clicked)

        # 菜单按钮
        self.menu_btn = QPushButton()
        self.menu_btn.setFixedSize(18, 18)
        self.menu_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover { background: #F4F4F4; }
            QPushButton:pressed { background: #666666; }
        """)
        self.menu_btn.setIcon(QIcon("ui/icon/知识库/icon_知识库_菜单.png"))
        self.setup_menu()
        self.menu_btn.clicked.connect(self.show_menu)

        topLayout.addWidget(self.pathLabel)
        topLayout.addStretch()
        topLayout.addWidget(self.menu_btn)

        mainLayout.addWidget(topWidget)

        # ============ 主内容区域 ============
        contentWidget = QWidget()
        contentLayout = QHBoxLayout(contentWidget)
        contentLayout.setContentsMargins(0, 0, 0, 0)
        contentLayout.setSpacing(0)

        # 左侧侧边栏
        self.sidebar = QWidget()
        self.sidebar.setStyleSheet("""
            width: 243px;
            height: 655px;
            background: #FFFFFF;
            border-radius: 0px 0px 0px 10px;
        """)
        self.init_sidebar()

        # 右侧内容区
        self.stackedWidget = QStackedWidget()
        self.init_right_panes()
        stack_layout = QVBoxLayout()
        stack_layout.setContentsMargins(24, 24, 24, 24)
        stack_layout.addWidget(self.stackedWidget)

        contentLayout.addWidget(self.sidebar)
        contentLayout.addLayout(stack_layout)

        mainLayout.addWidget(contentWidget)

    def init_sidebar(self):
        layout = QVBoxLayout(self.sidebar)
        layout.setSpacing(16)

        # 知识库图片
        imgLabel = QLabel()
        imgLabel.setPixmap(QPixmap("ui/icon/知识库/icon_知识库_通用.png").scaled(195, 96))
        imgLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(imgLabel)

        # 知识库名称
        nameLabel = QLabel(self.current_kb_name)
        nameLabel.setStyleSheet("""
            font-family: 'Source Han Sans SC';
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            line-height: 20px;
        """)
        nameLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(nameLabel)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #E5E5E5;")
        line.setFixedSize(219, 1)
        layout.addWidget(line)

        # 功能按钮
        self.btn_dataset = self.create_sidebar_btn("数据集", "icon_知识库_数据集.png")
        self.btn_recall = self.create_sidebar_btn("召回测试", "icon_知识库_召回测试.png")
        self.btn_config = self.create_sidebar_btn("配置", "icon_知识库_配置.png")

        layout.addWidget(self.btn_dataset)
        layout.addWidget(self.btn_recall)
        layout.addWidget(self.btn_config)
        layout.addStretch()

        # 连接按钮信号
        self.btn_dataset.clicked.connect(lambda: self.switch_page(0))
        self.btn_recall.clicked.connect(lambda: self.switch_page(1))
        self.btn_config.clicked.connect(lambda: self.switch_page(2))

    def create_sidebar_btn(self, text, icon):
        btn = QPushButton()
        btn.setFixedSize(195, 32)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding-left: 12px;
                font-family: 'Source Han Sans SC';
                font-size: 14px;
                color: #333333;
                border-radius: 4px;
            }
            QPushButton:hover { background: #F5F5F5; }
            QPushButton:pressed { background: #E5E5E5; }
        """)
        btn.setIcon(QIcon(f"ui/icon/{icon}"))
        btn.setIconSize(QSize(16, 16))
        btn.setText(text)
        return btn

    def init_right_panes(self):
        # 数据集页面
        self.dataset_page = DatasetPage(current_kb=self.current_kb, parent=self)
        self.recall_page = RecallPage(current_kb=self.current_kb)  # 占位页面
        self.config_page = ConfigurationPage(current_kb=self.current_kb)  # 占位页面

        self.stackedWidget.addWidget(self.dataset_page)
        self.stackedWidget.addWidget(self.recall_page)
        self.stackedWidget.addWidget(self.config_page)

    def on_nav_clicked(self, link):
        from ui.knowledge_base.knowledge_base_home import KnowledgeBaseHome
        self.knowledge_base_home = KnowledgeBaseHome()
        self.knowledge_base_home.show()
        self.close()

    def setup_menu(self):
        # 创建QMenu并设置样式
        self.menu = QMenu(self)
        self.menu.setFixedSize(182, 103)
        self.menu.setStyleSheet("""
            QMenu {
                background: #FFFFFF;
                border-radius: 6px;
                box-shadow: 0px 2px 10px rgba(0, 0, 0, 0.3);
            }
            QMenu::item {
                height: 28px;
                min-width: 174px;
                background: #FFFFFF;
                border-bottom: 1px solid #E0E0E0;
                margin: 0 0 9px 0;
                padding-left: 15px;
                padding-right: 8px;
                icon-size: 16px 16px;
                spacing: 8px;
                font-family: 'Source Han Sans SC';
                font-size: 14px;
                color: #333333;
                font-weight:400;
            }
            QMenu::item:last {
                border-bottom: none;
                margin-bottom: 0;
            }
            QMenu::item:selected {
                background: #F4F4F4;
                border-color: #CCCCCC;
            }
            QMenu::icon { 
                left: 15px;
            }
        """)

        # 添加菜单项
        menu_items = [
            ("知识库设置", "icon_知识库_知识库设置.png", self.on_settings),
            ("关于", "icon_知识库_关于.png", self.on_about),
            ("关闭", "icon_知识库_关闭.png", self.on_exit)
        ]

        for text, icon, callback in menu_items:
            action = QAction(QIcon(f"ui/icon/{icon}"), text, self)
            action.triggered.connect(callback)
            self.menu.addAction(action)

    def show_menu(self):
        btn_bottom_right = self.menu_btn.rect().bottomRight()
        global_pos = self.menu_btn.mapToGlobal(btn_bottom_right)
        adjusted_x = global_pos.x() - 170
        adjusted_y = global_pos.y() + 5
        self.menu.exec_(QPoint(adjusted_x, adjusted_y))

    def on_settings(self):
        print("打开知识库设置")

    def on_about(self):
        print("打开关于页面")

    def on_exit(self):
        self.close()


    def center_on_screen(self):
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        window_size = self.frameGeometry()
        self.move(
            (screen_geometry.width() - window_size.width()) // 2,
            (screen_geometry.height() - window_size.height()) // 2
        )


def main():
    app = QApplication(sys.argv)
    window = EnterKnowledgeBase()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()