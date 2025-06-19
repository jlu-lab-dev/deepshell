import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QSpacerItem, QSizePolicy, QAction, QMenu, QToolButton, QGridLayout
)
from PyQt5.QtGui import QIcon, QPixmap, QFont
from PyQt5.QtCore import Qt, QSize, QPoint
from ui.knowledge_base.create_knowledge_base import CreateKnowledgeBaseWidget
from database.repository.knowledge_base_repository import KnowledgeBaseRepository
from ui.knowledge_base.enter_knowledge_base import EnterKnowledgeBase
from config.config_manager import ConfigManager


class KnowledgeBaseHome(QWidget):
    def __init__(self):
        super().__init__()
        self.knowledge_bases = None
        self.initUI()
        self.center_on_screen()

        self.kb_repo = KnowledgeBaseRepository()

        #初始化时加载知识库
        self.load_knowledge_bases()


    def load_knowledge_bases(self):
        """加载知识库，更新页面"""
        #获取所有知识库
        self.knowledge_bases = self.kb_repo.list_knowledge_bases()

        # 清理旧内容
        if hasattr(self, 'kb_grid'):
            while self.kb_grid.count():
                item = self.kb_grid.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        #动态更新页面
        if self.knowledge_bases and len(self.knowledge_bases) > 0:
            # 当有知识库时，在 infoLabel 下方显示“请选择您要使用的知识库：”
            self.infoLabel.setText("请选择您要使用的知识库：")
            self.show_kb_grid()
        else:
            # 当没有知识库时，infoLabel显示提示信息
            self.infoLabel.setText("当前尚未创建任何知识库，请先点击右侧按钮创建一个知识库。")
            if hasattr(self, 'grid_widget'):
                self.grid_widget.hide()

    def show_empty_prompt(self):
        """显示空状态提示"""
        self.infoLabel.show()
        if hasattr(self, 'grid_widget'):
            self.grid_widget.hide()

    def show_kb_grid(self):
        """显示知识库网格"""
        # 清理旧的内容
        if hasattr(self, 'grid_widget'):
            self.grid_widget.deleteLater()
            del self.grid_widget
        if hasattr(self, 'grid_spacing_item'):
            self.contentLayout.removeItem(self.grid_spacing_item)
            del self.grid_spacing_item

        # 创建网格容器
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background: transparent;")
        self.kb_grid = QGridLayout(self.grid_widget)
        self.kb_grid.setContentsMargins(0, 0, 0, 0)
        self.kb_grid.setHorizontalSpacing(36)
        self.kb_grid.setVerticalSpacing(36)

        # 添加知识库卡片
        for i, kb in enumerate(self.knowledge_bases):
            row = i // 5
            col = i % 5
            kb_card = self.create_kb_card(kb)
            self.kb_grid.addWidget(kb_card, row, col)

        self.grid_spacing_item = QSpacerItem(0, 18, QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.contentLayout.insertSpacerItem(3, self.grid_spacing_item)
        self.contentLayout.insertWidget(4, self.grid_widget)

    def create_kb_card(self, kb):
        """创建单个知识库卡片"""
        card = QPushButton()
        card.setFixedSize(195, 217)
        card.setCursor(Qt.PointingHandCursor)
        card.setStyleSheet("""
            QPushButton {
                background: #FFFFFF;
                border-radius: 8px;
                border: 1px solid #CCCCCC;
                padding: 0;
                overflow: hidden;
            }
            QPushButton:hover {
                border-color: #007AFF;
                background: #F5FAFF;
            }
        """)

        # 主布局
        main_layout = QVBoxLayout(card)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 上半部分：图片区域 ===
        image_label = QLabel()
        image_label.setStyleSheet("""
            QLabel {
                width: 195px;
                height: 96px;
                background: #DAE6F0;
                border-radius: 8px 8px 0px 0px;
            }
        """)

        # 加载图片并设置缩放
        pixmap = QPixmap("ui/icon/知识库/icon_知识库_通用.png")
        # 精确缩放填充整个区域
        scaled_pixmap = pixmap.scaled(
            195, 96,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
        image_label.setPixmap(scaled_pixmap)
        image_label.setScaledContents(True)

        main_layout.addWidget(image_label)

        # === 下半部分：信息区域 ===
        info_widget = QWidget()
        info_widget.setFixedHeight(121)
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setSpacing(6)

        # 知识库名称
        name_label = QLabel(kb.name)
        name_label.setStyleSheet("""
            QLabel {
                width: 168px;
                height: 34px;
                font-family: Source Han Sans SC;
                font-weight: 400;
                font-size: 14px;
                color: #333333;
                line-height: 20px;
            }
        """)
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)

        info_layout.addStretch()

        # 文档数信息
        doc_info = QHBoxLayout()
        doc_icon = QLabel()
        doc_icon.setStyleSheet("""
            width: 14px;
            height: 16px;
        """)
        doc_icon.setPixmap(QIcon("ui/icon/知识库/icon_知识库_文件.png").pixmap(14, 16))
        doc_label = QLabel("文档 ")
        doc_label.setStyleSheet("""
            width: 28px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #333333;
            line-height: 20px;
        """)
        doc_count = QLabel(f"{kb.document_count}")
        doc_count.setStyleSheet("""
            QLabel {
                width: 50px;
                height: 11px;
                font-family: Source Han Sans SC;
                font-weight: 400;
                font-size: 14px;
                color: #999999;
                line-height: 20px;
            }
        """)
        doc_info.addWidget(doc_icon)
        doc_info.addWidget(doc_label)
        doc_info.addWidget(doc_count)
        doc_info.addStretch()
        info_layout.addLayout(doc_info)

        # 创建时间
        time_info = QHBoxLayout()
        time_icon = QLabel()
        time_icon.setStyleSheet("""
            width: 16px;
            height: 14px;
        """)
        time_icon.setPixmap(QIcon("ui/icon/知识库/icon_知识库_日历.png").pixmap(16, 14))

        # 转换时间格式（假设create_time是datetime对象）
        create_time = kb.created_at.strftime("%d/%m/%Y %H:%M:%S")
        time_label = QLabel(create_time)
        time_label.setStyleSheet("""
            QLabel {
                width: 130px;
                height: 14px;
                font-family: Source Han Sans SC;
                font-weight: 400;
                font-size: 14px;
                color: #999999;
                line-height: 20px;
            }
        """)
        time_info.addWidget(time_icon)
        time_info.addWidget(time_label)
        time_info.addStretch()
        info_layout.addLayout(time_info)

        info_layout.addStretch()
        main_layout.addWidget(info_widget)

        # 绑定点击事件（需要传递kb对象）
        card.clicked.connect(lambda checked, k=kb: self.manage_knowledge_base(k))

        return card

    def manage_knowledge_base(self,kb):
        """管理知识库（示例）"""
        self.enter_window = EnterKnowledgeBase(kb)
        self.enter_window.show()
        self.close()

    def refresh_kb_list(self):
        """刷新知识库列表"""
        self.load_knowledge_bases()

    def initUI(self):
        # ============ 主部件整体设置 ============
        # self.setFixedSize(1252, 700)
        self.setFixedWidth(1252)
        self.setMinimumHeight(700)
        self.setStyleSheet("""
            QWidget#main_widget {
                background: #FFFFFF;
                border: 1px solid #000000;
                border-radius: 9px;
                border-top: 2px solid #F0F0F0;
            }
        """)

        self.setWindowTitle(f"{ConfigManager().app_config['name']} - 知识库")
        # self.setWindowIcon(QIcon("ui/icon/知识库/icon_知识库_logo.png"))
        self.setWindowIcon(QIcon("ui/icon/DeepShell/icon_app_logo_DeepShell_圆角.png"))

        # 整体布局
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.setSpacing(0)

        # ============ 顶部搜索框和菜单框区域 ============
        topWidget = QWidget()
        topWidget.setFixedSize(1250, 45)
        topWidget.setStyleSheet("""
            background: #FFFFFF;
            border-top: 1px solid #F0F0F0;
            border-bottom: 1px solid #F0F0F0;
        """)
        topLayout = QHBoxLayout(topWidget)
        topLayout.setContentsMargins(10, 5, 10, 5)
        topLayout.setSpacing(10)

        # 搜索框容器（包含输入框和按钮）
        search_container = QWidget()
        search_container.setFixedSize(314 + 32, 32)  # 固定容器尺寸
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索")
        self.search_input.setFixedSize(314,32)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #F4F4F4;
                border-radius: 6px 0 0 6px;
                padding: 0 12px;
                border: none;
            }
        """)

        # 搜索按钮
        self.search_btn = QPushButton()
        self.search_btn.setFixedSize(32, 32)  # 严格匹配指定尺寸
        self.search_btn.setStyleSheet("""
            QPushButton {
                background: #F4F4F4;
                border: none;
            }
            QPushButton:hover {
                background: #999999;
            }
            QPushButton:pressed {
                background: #666666;
            }
        """)
        self.search_btn.setIcon(QIcon("ui/icon/知识库/icon_知识库_搜索.png"))

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)

        # 菜单按钮
        self.menu_btn = QPushButton()
        self.menu_btn.setFixedSize(18, 18)
        self.menu_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                    }
                    QPushButton:hover {
                        background: #F4F4F4;
                    }
                    QPushButton:pressed {
                        background: #666666;
                    }
                """)
        self.menu_btn.setIcon(QIcon("ui/icon/知识库/icon_知识库_菜单.png"))

        self.setup_menu()

        topLayout.addWidget(search_container)
        topLayout.addStretch()
        topLayout.addWidget(self.menu_btn)

        self.menu_btn.clicked.connect(self.show_menu)

        mainLayout.addWidget(topWidget, 0, Qt.AlignTop)

        # ============ 主内容区域 ============
        contentWidget = QWidget()
        contentWidget.setFixedSize(1250, 655)
        contentWidget.setObjectName("content_widget")
        self.contentLayout = QVBoxLayout(contentWidget)
        self.contentLayout.setContentsMargins(72, 44, 72, 0)  # 左72 上44 右72

        # 主内容区域的样式（白底 + 圆角下边）
        contentWidget.setStyleSheet("""
                    QWidget#content_widget {
                        background: #FFFFFF;
                        border-radius: 0px 0px 10px 10px;
                    }
                """)

        # 头部布局（欢迎文字+按钮）
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(759)  # 设置水平间距

        # 欢迎文字
        welcomeLabel = QLabel("欢迎回来")
        welcomeLabel.setObjectName("welcome_label")
        welcomeLabel.setStyleSheet("""
            QLabel#welcome_label {
                color: #333333;
            }
        """)
        welcomeLabel.setFont(QFont("Source Han Sans SC", 24))

        # 创建知识库按钮
        createButton = QToolButton()
        createButton.setFixedSize(180, 42)
        createButton.setText("创建知识库")
        createButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        createButton.setIcon(QIcon("ui/icon/知识库/icon_知识库_加号.png"))
        createButton.setIconSize(QSize(14, 14))

        # 通过样式表设置内边距（padding）可以调整图标和文字之间的间距
        createButton.setStyleSheet("""
            QToolButton {
                background: #007AFF;
                border-radius: 8px;
                color: #FFFFFF;
                font-family: "Source Han Sans SC";
                font-size: 16px;
                padding-left: 15px;
                text-align: center;
            }
            QToolButton::icon {
                width: 14px;
                height: 14px;
                left: 8px;
            }
            QToolButton::menu-indicator { image: none; }
            QToolButton:hover { background: #3399FF; }
            QToolButton:pressed { background: #0060D9; }
        """)

        createButton.clicked.connect(self.open_create_kb_page)

        header_layout.addWidget(welcomeLabel)
        header_layout.addWidget(createButton)

        self.contentLayout.addLayout(header_layout)
        self.contentLayout.addSpacing(20)

        # 提示文字（使用绝对定位）
        self.infoLabel = QLabel("", contentWidget)
        self.infoLabel.setObjectName("info_label")
        self.infoLabel.setStyleSheet("""
                QLabel#info_label {
                    height: 15px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 14px;
                    color: #333333;
                }
            """)
        fontInfo = QFont("Source Han Sans SC", 14)
        self.infoLabel.setFont(fontInfo)

        self.contentLayout.addWidget(self.infoLabel, alignment=Qt.AlignLeft)
        self.contentLayout.addStretch()

        # 将内容区域加入主布局
        mainLayout.addWidget(contentWidget)

        self.setLayout(mainLayout)

    def setup_menu(self):
        # 创建QMenu并设置样式
        self.menu = QMenu(self)
        self.menu.setFixedSize(182, 103)  # 严格符合设计尺寸
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
            QMenu::item:first {
                border-top: none;
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
        # 计算菜单位置（保持原有正确逻辑）
        btn_bottom_right = self.menu_btn.rect().bottomRight()
        global_pos = self.menu_btn.mapToGlobal(btn_bottom_right)

        # 根据设计稿调整偏移量
        adjusted_x = global_pos.x() - 170  # 182-12(按钮右边距)
        adjusted_y = global_pos.y() + 5

        # 设置菜单固定尺寸
        self.menu.setFixedSize(182, 103)

        # 显示在调整后的位置
        self.menu.exec_(QPoint(adjusted_x, adjusted_y))

    def on_settings(self):
        print("打开知识库设置")

    def on_about(self):
        print("打开关于页面")

    def on_exit(self):
        self.close()

    def mousePressEvent(self, event):

        super().mousePressEvent(event)

    def center_on_screen(self):
        """ 将窗口居中到主屏幕 """
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        window_size = self.frameGeometry()
        self.move(
            (screen_geometry.width() - window_size.width()) // 2,
            (screen_geometry.height() - window_size.height()) // 2
        )

    def open_create_kb_page(self):
        # 创建知识库窗口
        create_kb_widget = CreateKnowledgeBaseWidget(parent=self)

        # 获取按钮的绝对坐标
        button = self.sender()  # 获取触发按钮
        button_global_pos = button.mapToGlobal(QPoint(0, 0))

        # 计算目标位置（窗口右上角坐标）
        window_width = create_kb_widget.width()
        target_x = button_global_pos.x() - 64 - window_width  # 左边64px
        target_y = button_global_pos.y() + button.height() + 75  # 下边75px

        # 防止窗口超出屏幕
        screen = QApplication.primaryScreen().availableGeometry()
        if target_x < screen.left():
            target_x = screen.left()
        if target_y + create_kb_widget.height() > screen.bottom():
            target_y = screen.bottom() - create_kb_widget.height()

        # 设置窗口位置
        create_kb_widget.move(target_x, target_y)
        create_kb_widget.show()




def main():
    app = QApplication(sys.argv)
    window = KnowledgeBaseHome()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
