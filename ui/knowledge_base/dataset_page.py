from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QLabel, QTableWidgetItem, QPushButton, QVBoxLayout, QFrame, \
    QLineEdit, QTableWidget, QDialog, QMessageBox

from database.repository.knowledge_base_repository import KnowledgeBaseRepository
from rag.rag_manager import RAGManager
from ui.knowledge_base.upload_file import UploadDialog


class DatasetPage(QWidget):
    def __init__(self,current_kb=None,parent=None):
        super().__init__(parent)
        self.current_kb = current_kb
        self.mainwindow = parent
        self.repo = KnowledgeBaseRepository()
        self.setFixedSize(959, 607)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background: #FFFFFF; border-radius: 8px; border: 1px solid #E6E6E6;")
        self.initUI()
        self.init_table_config()


    def init_table_config(self):
        """初始化表格列配置"""
        self.tableWidget.setColumnWidth(0, 210)  # 名称
        self.tableWidget.setColumnWidth(1, 100)  # 分块数
        self.tableWidget.setColumnWidth(2, 200)  # 上传日期
        self.tableWidget.setColumnWidth(3, 100)  # 启用 (Index changed from 4 to 3)
        self.tableWidget.setColumnWidth(4, 120)  # 状态 (Index changed from 5 to 4)
        self.tableWidget.setColumnWidth(5, 180)  # 操作 (Index changed from 6 to 5)


    def load_files(self, documents):
        """加载文档数据到表格"""
        self.tableWidget.setRowCount(0)

        for doc in documents:
            row = self.tableWidget.rowCount()
            self.tableWidget.insertRow(row)

            # ====== 文件名称列 ======
            file_widget = QWidget()
            file_layout = QHBoxLayout(file_widget)
            file_layout.setContentsMargins(6, 0, 0, 0)
            file_layout.setSpacing(8)
            file_widget.setStyleSheet("""
                        QWidget {
                            border: none;
                            background: transparent;
                        }
                    """)

            #复选框
            checkbox = QCheckBox()
            """目前默认False"""
            checkbox.setChecked(False)
            checkbox.setStyleSheet("""
                            QCheckBox::indicator {
                                width: 16px;
                                height: 16px;
                            }
                            QCheckBox { border: none; }
                        """)
            file_layout.addWidget(checkbox)

            # 文件类型图标
            icon_label = QLabel()
            icon_path = self.get_file_icon(doc.filename)
            icon_label.setPixmap(QPixmap(icon_path).scaled(25, 25))
            file_layout.addWidget(icon_label)
            icon_label.setStyleSheet("""border:none;""")

            # 文件名
            name_label = QLabel(doc.filename)
            name_label.setStyleSheet("""
                            font-family: 'Source Han Sans SC';
                            font-weight: 400;
                            font-size: 14px;
                            color: #333333;
                            border: none;
                        """)
            file_layout.addWidget(name_label)
            file_layout.addStretch()

            self.tableWidget.setCellWidget(row, 0, file_widget)

            # 分块数
            self.tableWidget.setItem(row, 1, QTableWidgetItem(str(doc.chunk_count)))

            # 上传日期
            upload_time = doc.created_at.strftime("%d/%m/%Y %H:%M:%S")
            self.tableWidget.setItem(row, 2, QTableWidgetItem(upload_time))

            # 启用状态复选框 (Index changed from 4 to 3)
            """待精细"""
            self.tableWidget.setItem(row, 3, QTableWidgetItem("启用" if doc.status == "active" else "未启用"))

            # 解析状态 (Index changed from 5 to 4)
            """目前先固定解析成功，后期根据实际调用get_status_style"""
            status_label = QLabel("解析成功")
            status_label.setAlignment(Qt.AlignCenter)
            status_label.setStyleSheet("""
                            font-family: 'Source Han Sans SC';
                            font-weight: 400;
                            font-size: 14px;
                            color: #00CC00;
                            background: #FFFFFF;
                            border-radius: 4px;
                            border: 1px solid #00CC00;
                            padding: 2px 8px;
                        """)
            self.tableWidget.setCellWidget(row, 4, status_label) # Index changed from 5 to 4

            # 操作按钮 (Index changed from 6 to 5)
            btn_container = QWidget()
            btn_layout = QHBoxLayout()
            btn_container.setLayout(btn_layout)

            delete_btn = QPushButton("删除")
            delete_btn.setFixedSize(60, 24)
            delete_btn.setStyleSheet("""
                QPushButton {
                    background: #FF3B30; 
                    color: white;
                    border-radius: 4px;
                }
                QPushButton:hover { background: #FF1A1A; }
            """)
            # Connect the delete button click signal
            delete_btn.clicked.connect(lambda _, d_id=doc.id, r=row: self.delete_document(d_id, r))
            """这部分待添加各种action的icon以及单击事件"""
            # parse_btn = QPushButton("重新解析")
            # parse_btn.setFixedSize(80, 24)
            # parse_btn.setStyleSheet("""
            #     QPushButton {
            #         background: #007AFF;
            #         color: white;
            #         border-radius: 4px;
            #     }
            #     QPushButton:hover { background: #0066CC; }
            # """)

            # btn_layout.addWidget(parse_btn)
            btn_layout.addWidget(delete_btn)
            self.tableWidget.setCellWidget(row, 5, btn_container) # Index changed from 6 to 5

    def get_status_style(self, status):
        """根据状态获取样式"""
        color_map = {
            "解析成功": "#34C759",
            "解析中": "#FF9500",
            "解析失败": "#FF3B30",
            "等待解析": "#AEAEB2"
        }
        return f"""
            background: {color_map.get(status, '#AEAEB2')};
            color: white;
            border-radius: 4px;
            padding: 2px 8px;
        """

    def get_file_icon(self, filename):
        """根据文件扩展名获取图标路径"""
        ext = filename.split('.')[-1].lower()
        icon_map = {
            'txt': 'icon_知识库_文件_txt.png',
            'pdf': 'icon_知识库_文件_pdf.png',
            'docx': 'icon_知识库_文件_word.png',
            'xlsx': 'icon_知识库_文件_excel.png'
        }
        return f"ui/icon/{icon_map.get(ext)}"

    def initUI(self):

        # 主布局：上下布局
        mainLayout = QVBoxLayout(self)
        mainLayout.setContentsMargins(24, 24, 24, 24)
        mainLayout.setSpacing(16)

        # 1. 顶部标题及说明区域
        headerLayout = QVBoxLayout()
        headerLayout.setSpacing(8)

        # 大标题：数据集
        titleLabel = QLabel("数据集")
        titleLabel.setStyleSheet("""
            font-family: Microsoft YaHei;
            font-weight: 400;
            font-size: 28px;
            color: #333333;
            border:none;
        """)
        headerLayout.addWidget(titleLabel)

        # 说明文字
        infoLabel = QLabel("解析成功后才能问答哦")
        infoLabel.setStyleSheet("""
            font-family: Microsoft YaHei;
            font-size: 14px;
            color: #999999;
            border:none
        """)
        headerLayout.addWidget(infoLabel)

        mainLayout.addLayout(headerLayout)

        # 2. 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #E6E6E6;")
        line.setFixedHeight(1)
        mainLayout.addWidget(line)

        # 3. 搜索与新增文件区域
        search_addLayout = QHBoxLayout()
        search_addLayout.addStretch()
        search_addLayout.setSpacing(12)

        search_container = QWidget()
        search_container.setFixedSize(314 + 32, 32)  # 固定容器尺寸
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(0)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索")
        self.search_input.setFixedSize(314, 32)
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

        search_addLayout.addWidget(search_container)

        # 新增文件按钮
        addFileBtn = QPushButton("新增文件")
        addFileBtn.setFixedSize(120, 36)
        addFileBtn.setStyleSheet("""
            QPushButton
                {   background: #007AFF;
                    border: none;
                    border-radius: 8px;
                    font-family: Microsoft YaHei;
                    font-size: 14px;
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
        search_addLayout.addWidget(addFileBtn)

        addFileBtn.clicked.connect(self.add_document)

        mainLayout.addLayout(search_addLayout)

        # 4. 文件列表区域（使用表格展示）
        self.tableWidget = QTableWidget(0, 6) # Changed column count from 7 to 6
        self.tableWidget.setStyleSheet("""
            QTableWidget {
                background: #FFFFFF;
                border: none;
                font-family: Microsoft YaHei;
                font-size: 14px;
                color: #333333;
            }
            QHeaderView::section {
                background-color: #F4F4F4;
                padding: 4px;
                border: 1px solid #E6E6E6;
                font-weight: bold;
            }
        """)
        self.tableWidget.setHorizontalHeaderLabels(
            ["名称", "分块数", "上传日期", "启用", "解析状态", "动作"] # Removed "解析方法"
        )
        self.tableWidget.verticalHeader().setVisible(False)
        self.tableWidget.setShowGrid(False)
        # 自适应表头宽度
        # header = self.tableWidget.horizontalHeader()
        # header.setSectionResizeMode(QHeaderView.Stretch)
        mainLayout.addWidget(self.tableWidget)

    def add_document(self):
        if hasattr(self, 'upload_dialog'):
            self.upload_dialog.close()
        self.upload_dialog = UploadDialog(self)  # 确保传递parent参数

        parent_rect = self.geometry()
        parent_center_x = parent_rect.x() + parent_rect.width() / 2
        parent_center_y = parent_rect.y() + parent_rect.height() / 2

        # 获取对话框的大小
        dialog_width = self.upload_dialog.width()
        dialog_height = self.upload_dialog.height()

        # 计算对话框的左上角位置
        dialog_x = parent_center_x - dialog_width / 2
        dialog_y = parent_center_y - dialog_height / 2

        # 设置对话框的位置
        self.upload_dialog.move(int(dialog_x), int(dialog_y))

        if self.upload_dialog.exec_() == QDialog.Accepted:
            rag_manager = RAGManager()
            success_count = 0

            for file_path in self.upload_dialog.get_selected_files():
                # TODO: 事务保证
                try:
                    # 添加到数据库
                    doc_data = {
                        'kb_id': self.current_kb.id,
                        'filename': Path(file_path).name,
                        'file_path': str(file_path),
                        'file_type': Path(file_path).suffix[1:]
                    }
                    doc_added = self.repo.add_document(doc_data)
                    success_count += 1
                    # TODO: 异步实现。只创建文档元信息到向量数据库，解析通过点击解析按钮后异步完成
                    # 上传到向量数据库
                    rag_manager.add_document(
                        file_path,
                        knowledge_base=self.current_kb.id,
                        doc_id=doc_added.id
                    )
                except Exception as e:
                    print(f"文件上传失败: {str(e)}")

            if success_count > 0:
                # 刷新表格
                self.mainwindow.load_documents()
                QMessageBox.information(self, "提示", f"成功上传{success_count}个文件")
            else:
                QMessageBox.warning(self, "提示", "文件上传失败，请检查日志")
    
    def delete_document(self, doc_id, row):
        """删除文件: 1. 数据库中的元信息 2. 向量数据库中的数据"""
        rag_manager = RAGManager()
        try:
            doc = self.repo.get_document_by_id(doc_id)
            if not doc:
                QMessageBox.warning(self, "错误", "找不到要删除的文件记录")
                return

            file_name = doc.filename
            reply = QMessageBox.question(self, "确认删除", f"确定要删除文件 {file_name} 吗？\n此操作将从数据库和向量存储中移除该文件及其相关数据。",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                rag_manager.delete_document(doc_id=doc_id)
                deleted_db = self.repo.delete_document(doc_id)
                if deleted_db:
                    self.tableWidget.removeRow(row)
                    QMessageBox.information(self, "提示", f"文件 {file_name} 删除成功")
                else:
                    QMessageBox.warning(self, "错误", f"从数据库删除文件 {file_name} 失败")

        except Exception as e:
            print(f"Error deleting file (doc_id: {doc_id}): {str(e)}")
            QMessageBox.critical(self, "删除失败", f"删除文件时发生错误: {str(e)}")
