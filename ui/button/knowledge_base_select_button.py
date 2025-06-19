from typing import Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QPushButton, QMenu, QWidgetAction, QHBoxLayout, QLabel, QWidget, QCheckBox
from PyQt5.QtGui import QIcon

from database.repository.knowledge_base_repository import KnowledgeBaseRepository


class KnowledgeBaseSelectButton(QPushButton):
    selection_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repository = KnowledgeBaseRepository()
        self.kb_dict = self.get_kb_dict_from_db()
        self.selected_kb_id_list = []
        self.init_ui()
        self.refresh_kb_list()

    def init_ui(self):
        self.setStyleSheet("""
        QPushButton{
                    width: 114px;
                    height: 36px;
                    background: #30425C;
                    border-radius: 8px;
                    opacity: 0.4;}
                """)

        # 图标
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setPixmap(QIcon("ui/icon/icon_输入框_知识库.png").pixmap(16, 16))

        # 模型名称
        self.name_label = QLabel("知识库")
        self.name_label.setStyleSheet("""
            width: 41px;
            height: 14px;
            font-family: Source Han Sans SC;
            font-weight: 400;
            font-size: 14px;
            color: #FFFFFF;
            line-height: 18px;
        """)

        # 下拉箭头
        arrow_label = QLabel()
        arrow_label.setFixedSize(16, 16)
        arrow_label.setStyleSheet("""
            background: rgba(51,51,51,0);
        """)
        arrow_label.setPixmap(QIcon("ui/icon/icon_输入框_下拉框.png").pixmap(16, 16))

        # 添加到布局
        layout = QHBoxLayout()
        layout.setSpacing(7)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.name_label)
        layout.addWidget(arrow_label, Qt.AlignRight)
        self.setLayout(layout)

        # 创建下拉菜单
        self.menu = QMenu(self)
        self.menu.setStyleSheet("""
            QMenu {
                background: #30425C;
                border-radius: 8px;
                opacity: 0.4;
            }
        """)

        # 初始化菜单选项
        self.update_menu_items()

        self.clicked.connect(self.show_menu)

    def create_menu_action(self, kb_id, kb_name):
        selected_label = QCheckBox()
        selected_label.setStyleSheet("""
                    QCheckBox {
                        background-color: #30425C;
                        border: 1px solid #808080;  /* 添加灰色边框 */
                        border-radius: 3px;         /* 轻微圆角 */
                        padding: 2px;               /* 增加内边距 */
                    }
                    QCheckBox::indicator {
                        width: 12px;
                        height: 8px;
                    }
                    QCheckBox::indicator:checked {
                        image: url(ui/icon/menu_select.png);
                    }
                    QCheckBox::indicator:unchecked {
                        image: none;
                    }
                    QCheckBox:hover {
                        border: 1px solid #A0A0A0;  /* 悬停时变浅灰 */
                    }
               """)
        selected_label.setFixedSize(16, 16)
        selected_label.setChecked(kb_id in self.selected_kb_id_list)
        selected_label.stateChanged.connect(
            lambda state, k_b=kb_id: self.update_selected_kb(k_b, state)
        )

        kb_name = QLabel(kb_name)
        kb_name.setStyleSheet("""
                        width: 192px;
                        height: 16px;
                        font-family: Source Han Sans SC;
                        font-weight: 400;
                        font-size: 14px;
                        color: #FFFFFF;
                    """)

        layout = QHBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(selected_label, 0, Qt.AlignVCenter)
        layout.addWidget(kb_name, 0, Qt.AlignVCenter)

        action_widget = QWidget()
        action_widget.setStyleSheet("""
            width: 222px;
            height: 24px;
            background: rgba(48,66,92,0);
            border-radius: 4px;
        """)
        action_widget.setLayout(layout)

        action = QWidgetAction(self.menu)
        action.setDefaultWidget(action_widget)
        action.triggered.connect(selected_label.toggle)  # 增加被选中的图标

        return action

    def update_menu_items(self):
        """更新菜单项，添加选中标记"""
        self.menu.clear()
        self.kb_dict = self.get_kb_dict_from_db()
        self.selected_kb_id_list = [kb for kb in self.selected_kb_id_list if kb in self.kb_dict]
        for kb_id, kb_name in self.kb_dict.items():
            action = self.create_menu_action(kb_id, kb_name)
            self.menu.addAction(action)
    
    def get_kb_dict_from_db(self) -> Dict[str, str]:
        """从数据库中获取知识库列表，返回一个字典，键是 id，值是 name"""
        try:
            kbs = self.repository.list_knowledge_bases()
            if kbs:
                return {kb.id: kb.name for kb in kbs}
            else:
                return {}
        except Exception as e:
            print("获取知识库失败{}:".format(e))
            return {}
    
    def refresh_kb_list(self):
        """刷新知识库列表并保持选中状态"""
        prev_selected = self.selected_kb_id_list.copy()
        self.kb_dict = self.get_kb_dict_from_db()
        self.selected_kb_id_list = [kb for kb in prev_selected if kb in self.kb_dict]

    def update_selected_kb(self, kb_id, state):
        """更新选中状态"""
        if state == Qt.Checked:
            if kb_id not in self.selected_kb_id_list:
                self.selected_kb_id_list.append(kb_id)
        else:
            if kb_id in self.selected_kb_id_list:
                self.selected_kb_id_list.remove(kb_id)
        self.selection_changed.emit(self.selected_kb_id_list)

    def show_menu(self):
        """显示前刷新菜单内容"""
        self.refresh_kb_list()
        self.menu.clear()

        # 添加"无"选项作为默认
        if not self.kb_dict:
            self.menu.addAction(self.create_menu_action(0, "无"))
        else:
            for kb_id, kb_name in self.kb_dict.items():
                self.menu.addAction(self.create_menu_action(kb_id, kb_name))

        # 显示菜单
        self.menu.exec_(self.mapToGlobal(self.rect().bottomLeft()))

