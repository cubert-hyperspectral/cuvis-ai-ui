"""Canvas item for a cuvis-ai node: the pipeline's node name, its class below."""

from __future__ import annotations

from typing import Any

from NodeGraphQt.constants import LayoutDirectionEnum
from NodeGraphQt.qgraphics.node_base import NodeItem
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsTextItem

# The class line is this many points smaller than the node name.
_CLASS_FONT_STEP = 1.5
# Opacity of the class line's colour, so the name stays the stronger label.
_CLASS_ALPHA = 170
# Free space beside the class line, so it never touches the node's edges.
_CLASS_SIDE_PADDING = 16.0


class CuvisNodeItem(NodeItem):
    """A NodeGraphQt node item with a second, smaller label line for the class.

    The title shows the node's name; the class line sits under the title band
    and above the ports. It is hidden in proxy mode (zoomed out) and in the
    vertical layout, where NodeGraphQt also drops the port names.
    """

    def __init__(self, name: str = "node", parent: Any = None) -> None:
        super().__init__(name, parent)
        self._class_item = QGraphicsTextItem("", self)
        font = self._text_item.font()
        if font.pointSizeF() > 0:
            font.setPointSizeF(max(font.pointSizeF() - _CLASS_FONT_STEP, 6.0))
        else:
            font.setPixelSize(max(font.pixelSize() - 2, 8))
        self._class_item.setFont(font)

    @property
    def class_item(self) -> QGraphicsTextItem:
        """The text item of the class line."""
        return self._class_item

    def set_class_label(self, text: str) -> None:
        """Show ``text`` as the class line and lay the node out again."""
        if text == self._class_item.toPlainText():
            return
        self._class_item.setPlainText(text)
        if self.scene():
            self.draw_node()

    def _horizontal(self) -> bool:
        return self.layout_direction is LayoutDirectionEnum.HORIZONTAL.value

    def _class_line_height(self) -> float:
        if not self._class_item.toPlainText() or not self._horizontal():
            return 0.0
        return self._class_item.boundingRect().height()

    def _set_text_color(self, color: tuple[int, ...]) -> None:
        super()._set_text_color(color)
        red, green, blue = color[0], color[1], color[2]
        self._class_item.setDefaultTextColor(QColor(red, green, blue, _CLASS_ALPHA))

    def _calc_size_horizontal(self) -> tuple[float, float]:
        width, height = super()._calc_size_horizontal()
        if self._class_item.toPlainText():
            width = max(width, self._class_item.boundingRect().width() + _CLASS_SIDE_PADDING)
        return width, height

    # NodeItem's horizontal layout passes the title band's height to these three
    # hooks; the class line adds its own height there, so the node grows and the
    # ports and widgets start below the class line.

    def _set_base_size(self, add_w: float = 0.0, add_h: float = 0.0) -> None:
        super()._set_base_size(add_w, add_h + self._class_line_height())

    def align_ports(self, v_offset: float = 0.0) -> None:
        super().align_ports(v_offset + self._class_line_height())

    def align_widgets(self, v_offset: float = 0.0) -> None:
        super().align_widgets(v_offset + self._class_line_height())

    def _draw_node_horizontal(self) -> None:
        super()._draw_node_horizontal()
        # NodeItem's title band is the title's height plus 4
        title_height = self._text_item.boundingRect().height() + 4.0
        rect = self.boundingRect()
        class_width = self._class_item.boundingRect().width()
        self._class_item.setPos(rect.center().x() - class_width / 2, rect.y() + title_height)
        self._class_item.setVisible(bool(self._class_item.toPlainText()) and not self._proxy_mode)

    def _draw_node_vertical(self) -> None:
        super()._draw_node_vertical()
        self._class_item.setVisible(False)

    def set_proxy_mode(self, mode: bool) -> None:
        super().set_proxy_mode(mode)
        visible = not mode and self._horizontal() and bool(self._class_item.toPlainText())
        self._class_item.setVisible(visible)
