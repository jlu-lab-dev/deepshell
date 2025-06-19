from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, QPoint, QRect
from PyQt5.QtGui import QPainter, QBrush, QColor, QPen, QPainterPath


class DraggableDivider(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(14)  # 控件高度
        self.circle_radius = 7  # 圆球半径
        self.circle_pos = 50  # 初始位置百分比
        self.dragging = False
        self.line_width = 4  # 横线粗细
        self.setMouseTracking(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        line_y = self.height() // 2
        circle_x = int(self.width() * self.circle_pos / 100)

        # 绘制圆角横线
        self._draw_rounded_line(painter, line_y, circle_x)

        # 绘制可拖动圆球
        self._draw_draggable_circle(painter, circle_x, line_y)

    def _draw_rounded_line(self, painter, line_y, divider_x):
        """绘制圆角横线（左蓝右灰）"""
        radius = self.line_width  # 圆角半径等于线宽

        # 左侧蓝色横线
        path_left = QPainterPath()
        path_left.addRoundedRect(0, line_y - self.line_width // 2,
                                 divider_x, self.line_width,
                                 radius, radius)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(66, 135, 245))
        painter.drawPath(path_left)

        # 右侧灰色横线
        path_right = QPainterPath()
        path_right.addRoundedRect(divider_x, line_y - self.line_width // 2,
                                  self.width() - divider_x, self.line_width,
                                  radius, radius)
        painter.setBrush(QColor(200, 200, 200))
        painter.drawPath(path_right)

    def _draw_draggable_circle(self, painter, circle_x, circle_y):
        """绘制可拖动圆球（白外蓝内）"""
        # 白色外圆
        painter.setBrush(QBrush(Qt.white))
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawEllipse(QPoint(circle_x, circle_y),
                            self.circle_radius, self.circle_radius)

        # 蓝色内圆（半径一半）
        inner_radius = self.circle_radius // 2
        painter.setBrush(QBrush(QColor(66, 135, 245)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(circle_x, circle_y),
                            inner_radius, inner_radius)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            circle_x = int(self.width() * self.circle_pos / 100)
            circle_y = self.height() // 2
            circle_rect = QRect(
                circle_x - self.circle_radius,
                circle_y - self.circle_radius,
                self.circle_radius * 2,
                self.circle_radius * 2
            )
            if circle_rect.contains(event.pos()):
                self.dragging = True

    def mouseMoveEvent(self, event):
        if self.dragging:
            x = max(self.circle_radius,
                    min(event.x(), self.width() - self.circle_radius))
            self.circle_pos = (x / self.width()) * 100
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = False

    def get_position(self):
        """获取当前分割位置百分比"""
        return self.circle_pos