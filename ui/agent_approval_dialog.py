"""DeepShell GUI 文件操作人工确认窗口。

所属模块：ui。
职责：显示完整待写内容与内容摘要，采用非阻塞 open() 等待用户选择。
Dialog 本身不接触文件系统，批准操作只能由 Controller 交回 ToolExecutor。
"""
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QDialog, QLabel, QPlainTextEdit, QDialogButtonBox,
                             QVBoxLayout)


class AgentApprovalDialog(QDialog):
    def __init__(self, filename: str, workspace: str, content: str, digest: str, parent=None, operation=False):
        super().__init__(parent)
        self.setWindowTitle('DeepShell · 人工确认工具操作' if operation else 'DeepShell · 人工确认文件创建')
        self.setWindowModality(Qt.WindowModal)
        self.resize(570, 400)
        layout = QVBoxLayout(self)

        # 路径、摘要、全文必须在用户确认前展示，而不是只展示截断预览。
        heading = (
            f'工具：{filename}\n操作影响：{workspace}\n'
            f'请求 SHA-256：{digest}\n请核对下方完整参数；仅本次批准有效。'
        ) if operation else (
            'Agent 请求创建新文本文件。此操作仅在点击「批准创建」后执行。\n'
            f'工作目录：{workspace}\n文件名：{filename}\n'
            f'内容 SHA-256：{digest}\n（文件已存在时不会覆盖）')
        label = QLabel(heading, self)
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(label)

        preview = QPlainTextEdit(self)
        preview.setReadOnly(True)
        preview.setPlainText(content)
        layout.addWidget(preview)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.button(QDialogButtonBox.Ok).setText('批准本次操作' if operation else '批准创建')
        buttons.button(QDialogButtonBox.Cancel).setText('拒绝')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        # 超时自动拒绝，避免过期弹窗一直占据界面。
        self._expiry_timer = QTimer(self)
        self._expiry_timer.setSingleShot(True)
        self._expiry_timer.timeout.connect(self.reject)
        self.finished.connect(self._expiry_timer.stop)
        self._expiry_timer.start(60000)
