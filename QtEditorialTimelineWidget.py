from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsItem,
)
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF, QFont
from PySide6.QtCore import Qt, QRectF, QTimer, QPointF

# --- Default Constants (can be overridden by theme) ---
DEFAULT_CONSTANTS = {
    "LEFT_MARGIN": 150,
    "TOP_MARGIN": 30,
    "BOTTOM_MARGIN": 20,
    "TRACK_SPACING": 2,
    "BASE_PIXELS_PER_FRAME": 10,
    "DEFAULT_TRACK_HEIGHT": 60,
}

# --- Default Themes ---
THEMES = {
    "dark": {
        "timeLabel_bg": "#141414",
        "timeLabel_text": "#FFFFFF",
        "ruler_bg": "#1E1E1E",
        "ruler_tick_major": "#FFFFFF",
        "ruler_tick_minor": "#808080",
        "playhead_color": "#FFA500",
        "track_header_bg": "#282828",
        "track_header_text": "#FFFFFF",
        "track_lane_bg1": "#323232",
        "track_lane_bg2": "#3E3E3E",
        "track_lane_border": "#505050",
        "clip_fill": "#6496C8",
        "clip_fill_selected": "#96C8FF",
        "clip_border": "#000000",
        "end_line_color": "#C83232",
        "background_color": "#111111",
    },
    "light": {
        "timeLabel_bg": "#F0F0F0",
        "timeLabel_text": "#000000",
        "ruler_bg": "#E0E0E0",
        "ruler_tick_major": "#000000",
        "ruler_tick_minor": "#808080",
        "playhead_color": "#FF8C00",
        "track_header_bg": "#D0D0D0",
        "track_header_text": "#000000",
        "track_lane_bg1": "#E8E8E8",
        "track_lane_bg2": "#F0F0F0",
        "track_lane_border": "#A0A0A0",
        "clip_fill": "#90CAF9",
        "clip_fill_selected": "#64B5F6",
        "clip_border": "#000000",
        "end_line_color": "#E53935",
        "background_color": "#FFFFFF",
    },
}


def get_theme(config=None):
    """Return a complete theme dictionary.

    If config is a string and matches one of THEMES, return that 
    theme merged with default constants.
    If config is a dict, merge it with the dark theme defaults.
    Otherwise, return the dark theme merged with default constants.
    """
    theme = THEMES.get("dark").copy()
    if isinstance(config, str) and config in THEMES:
        theme = THEMES[config].copy()
    elif isinstance(config, dict):
        # Start with dark theme defaults and update with provided values.

        theme = THEMES["dark"].copy()
        theme.update(config)
    # Merge in the default constants (allowing overrides)

    full_theme = DEFAULT_CONSTANTS.copy()
    full_theme.update(theme)
    return full_theme


# --- Helper Function ---
def frames_to_timecode(frames, fps=24):
    frames = int(round(frames))
    seconds = frames // fps
    frames_rem = frames % fps
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds_rem = seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds_rem:02}:{frames_rem:02}"


# --- Data Classes ---
class TrackData:
    def __init__(self, name, height=None):
        self.name = name
        self.height = (
            height 
            if height is not None 
            else DEFAULT_CONSTANTS["DEFAULT_TRACK_HEIGHT"]
        )
        self.clips = []  # list of ClipData

    def add_clip(self, clip):
        self.clips.append(clip)

class ClipData:
    def __init__(self, title, start_frame, duration_frames):
        self.title = title
        self.start_frame = start_frame
        self.duration_frames = duration_frames


# --- Graphics Items ---
# Each item now accepts a theme dict and uses its color settings.
class TimeLabelItem(QGraphicsItem):
    def __init__(self, playhead_frame=0, theme=None, parent=None):
        super().__init__(parent)
        self.playhead_frame = playhead_frame
        self.theme = theme
        self.setZValue(20)

    def boundingRect(self):
        return QRectF(0, 0, self.theme["LEFT_MARGIN"], self.theme["TOP_MARGIN"])

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        painter.fillRect(rect, QColor(self.theme["timeLabel_bg"]))
        painter.setPen(QColor(self.theme["timeLabel_text"]))
        painter.setFont(QFont("Sans", 10))
        text = frames_to_timecode(self.playhead_frame)
        painter.drawText(rect, Qt.AlignCenter, text)

    def updateTime(self, frame):
        self.playhead_frame = int(round(frame))
        self.update()


class RulerItem(QGraphicsItem):
    def __init__(self, theme=None, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setZValue(10)

    def boundingRect(self):
        width = self.scene().width() - self.theme["LEFT_MARGIN"]
        return QRectF(0, 0, width, self.theme["TOP_MARGIN"])

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        painter.fillRect(rect, QColor(self.theme["ruler_bg"]))
        fps = 24
        view = self.scene().views()[0]
        h_zoom = view.h_zoom
        scale = self.theme["BASE_PIXELS_PER_FRAME"] * h_zoom
        x = 0
        while x < rect.width():
            frame = x / scale
            if int(frame) % fps == 0:
                painter.setPen(QPen(QColor(self.theme["ruler_tick_major"])))
                painter.drawLine(x, rect.bottom(), x, rect.bottom() - 15)
                timecode = frames_to_timecode(frame, fps)
                painter.drawText(x + 2, rect.bottom() - 17, timecode)
            else:
                painter.setPen(QPen(QColor(self.theme["ruler_tick_minor"])))
                painter.drawLine(x, rect.bottom(), x, rect.bottom() - 5)
            x += scale


class PlayheadTriangleItem(QGraphicsItem):
    def __init__(self, timeline, theme=None, parent=None):
        super().__init__(parent)
        self.timeline = timeline
        self.theme = theme
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsScenePositionChanges
            | QGraphicsItem.ItemIgnoresTransformations
        )
        self.setZValue(1000)
        self.dragging = False

    def boundingRect(self):
        return QRectF(-10, 0, 20, self.theme["TOP_MARGIN"])

    def paint(self, painter, option, widget):
        triangle_height = 15
        triangle_width = 15
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(self.theme["playhead_color"]))
        triangle = QPolygonF(
            [
                QPointF(
                    -triangle_width / 2, 
                    self.theme["TOP_MARGIN"] - triangle_height
                ),
                QPointF(
                    triangle_width / 2, 
                    self.theme["TOP_MARGIN"] - triangle_height
                ),
                QPointF(0, self.theme["TOP_MARGIN"]),
            ]
        )
        painter.drawPolygon(triangle)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            new_pos.setY(0)
            return new_pos
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.updatePlayhead()

    def mouseReleaseEvent(self, event):
        self.updatePlayhead()
        self.dragging = False
        super().mouseReleaseEvent(event)

    def updatePlayhead(self):
        view = self.scene().views()[0]
        new_frame = (self.pos().x() - self.theme["LEFT_MARGIN"]) / (
            self.theme["BASE_PIXELS_PER_FRAME"] * view.h_zoom
        )
        self.timeline.setPlayheadFrame(new_frame)


class PlayheadLineItem(QGraphicsItem):
    def __init__(self, timeline, theme=None, parent=None):
        super().__init__(parent)
        self.timeline = timeline
        self.theme = theme
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsScenePositionChanges
            | QGraphicsItem.ItemIgnoresTransformations
        )
        self.setZValue(1000)
        self.dragging = False

    def boundingRect(self):
        height = self.scene().height()
        return QRectF(-2, 0, 4, height - 0)

    def paint(self, painter, option, widget):
        painter.fillRect(
            self.boundingRect(), 
            QColor(self.theme["playhead_color"])
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            new_pos.setY(self.theme["TOP_MARGIN"])
            return new_pos
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.updatePlayhead()

    def mouseReleaseEvent(self, event):
        self.updatePlayhead()
        self.dragging = False
        super().mouseReleaseEvent(event)

    def updatePlayhead(self):
        view = self.scene().views()[0]
        new_frame = (self.pos().x() - self.theme["LEFT_MARGIN"]) / (
            self.theme["BASE_PIXELS_PER_FRAME"] * view.h_zoom
        )
        self.timeline.setPlayheadFrame(new_frame)


class EndLineItem(QGraphicsItem):
    def __init__(self, timeline, theme=None, parent=None):
        super().__init__(parent)
        self.timeline = timeline
        self.theme = theme
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsScenePositionChanges
            | QGraphicsItem.ItemIgnoresTransformations
        )
        self.setZValue(900)
        self.dragging = False

    def boundingRect(self):
        height = self.scene().height() - self.theme["BOTTOM_MARGIN"]
        return QRectF(-2, 0, 4, height - 0)

    def paint(self, painter, option, widget):
        painter.fillRect(
            self.boundingRect(), 
            QColor(self.theme["end_line_color"])
        )

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            new_pos.setY(self.theme["TOP_MARGIN"])
            view = self.scene().views()[0]
            new_frame = (new_pos.x() - self.theme["LEFT_MARGIN"]) / (
                self.theme["BASE_PIXELS_PER_FRAME"] * view.h_zoom
            )
            min_end = self.timeline.minimum_end_frame()
            if new_frame < min_end:
                new_frame = min_end
                new_x = (
                    self.theme["LEFT_MARGIN"]
                    + new_frame 
                    * self.theme["BASE_PIXELS_PER_FRAME"] 
                    * view.h_zoom
                )
                new_pos.setX(new_x)
            return new_pos
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self.dragging = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self.updateEndFrame()

    def mouseReleaseEvent(self, event):
        self.updateEndFrame()
        self.dragging = False
        super().mouseReleaseEvent(event)

    def updateEndFrame(self):
        view = self.scene().views()[0]
        new_frame = (self.pos().x() - self.theme["LEFT_MARGIN"]) / (
            self.theme["BASE_PIXELS_PER_FRAME"] * view.h_zoom
        )
        self.timeline.setEndFrame(new_frame)


class TrackHeaderItem(QGraphicsItem):
    def __init__(self, track_data, theme=None, parent=None):
        super().__init__(parent)
        self.track_data = track_data
        self.theme = theme
        self.setZValue(5)

    def boundingRect(self):
        v_zoom = self.scene().views()[0].v_zoom
        rect = QRectF(
            0, 0, self.theme["LEFT_MARGIN"], 
            self.track_data.height * v_zoom
        )
        return rect

    def paint(self, painter, option, widget):
        rect = self.boundingRect()
        painter.fillRect(rect, QColor(self.theme["track_header_bg"]))
        painter.setPen(QColor(self.theme["track_header_text"]))
        painter.setFont(QFont("Sans", 10))
        painter.drawText(
            rect.adjusted(5, 0, -5, 0),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.track_data.name,
        )
        painter.setPen(
            QPen(
                QColor(
                    self.theme.get(
                        "track_header_border", self.theme["track_lane_border"]
                    )
                )
            )
        )
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())


class TrackLaneItem(QGraphicsItem):
    def __init__(self, track_data, theme=None, parent=None):
        super().__init__(parent)
        self.track_data = track_data
        self.theme = theme
        self.rect = QRectF()
        self.setZValue(0)

    def boundingRect(self):
        return self.rect

    def setGeometry(self, x, y, width, height):
        self.rect = QRectF(x, y, width, height)
        self.update()

    def paint(self, painter, option, widget):
        # Alternate lane color based on track name (for simplicity)
        bg = (
            QColor(self.theme["track_lane_bg1"])
            if (self.track_data.name.endswith("1"))
            else QColor(self.theme["track_lane_bg2"])
        )
        painter.fillRect(self.rect, bg)
        painter.setPen(QPen(QColor(self.theme["track_lane_border"])))
        painter.drawRect(self.rect)


class ClipItem(QGraphicsItem):
    SNAP_TOLERANCE = 1

    def __init__(self, clip_data, track_data, theme=None, parent=None):
        super().__init__(parent)
        self.clip_data = clip_data
        self.track_data = track_data
        self.theme = theme
        self.rect = QRectF()
        self.setFlags(
            QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable
        )
        self._fixed_y = 0

    def boundingRect(self):
        return self.rect

    def setGeometry(self, x, y, width, height):
        self.rect = QRectF(0, 0, width, height)
        self.setPos(x, y)
        self._fixed_y = y
        self.update()

    def paint(self, painter, option, widget):
        fill = (
            QColor(self.theme["clip_fill_selected"])
            if self.isSelected()
            else QColor(self.theme["clip_fill"])
        )
        painter.fillRect(self.rect, fill)
        painter.setPen(QPen(QColor(self.theme["clip_border"])))
        painter.drawRect(self.rect)
        painter.setPen(QColor(self.theme["track_header_text"]))
        painter.setFont(QFont("Sans", 8))
        margin = 2
        start_tc = frames_to_timecode(self.clip_data.start_frame)
        end_tc = frames_to_timecode(
            self.clip_data.start_frame + self.clip_data.duration_frames
        )
        painter.drawText(
            self.rect.adjusted(margin, margin, 0, 0),
            Qt.AlignLeft | Qt.AlignTop,
            start_tc,
        )
        tw = painter.fontMetrics().horizontalAdvance(end_tc)
        painter.drawText(
            self.rect.adjusted(0, margin, -margin, 0),
            Qt.AlignRight | Qt.AlignTop,
            end_tc,
        )
        painter.drawText(self.rect, Qt.AlignCenter, self.clip_data.title)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            new_pos.setY(self._fixed_y)
            return new_pos
        return super().itemChange(change, value)

    def mousePressEvent(self, event):
        self._fixed_y = self.pos().y()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        view = self.scene().views()[0]

        # Compute the candidate frame from the current x position.
        original_candidate = round(
            (self.pos().x() - self.theme["LEFT_MARGIN"])
            / (self.theme["BASE_PIXELS_PER_FRAME"] * view.h_zoom)
        )

        # Build a list of possible snapping candidates (in frames)
        candidate_options = [original_candidate]
        for other in self.track_data.clips:
            if other is self.clip_data:
                continue
            other_end = other.start_frame + other.duration_frames

            # If the original candidate is within SNAP_TOLERANCE 
            # of another clip's end, add that option.
            if abs(original_candidate - other_end) <= self.SNAP_TOLERANCE:
                candidate_options.append(other_end)

            # If the end of our clip (if placed at candidate) would be within 
            # tolerance of another clip’s start, add that option.
            if (
                abs(
                    original_candidate
                    + self.clip_data.duration_frames
                    - other.start_frame
                )
                <= self.SNAP_TOLERANCE
            ):
                candidate_options.append(
                    other.start_frame - self.clip_data.duration_frames
                )

        # Choose the candidate that is closest to the original candidate.
        candidate = min(
            candidate_options, 
            key=lambda c: abs(c - original_candidate)
        )

        # Overlap check: if placing the clip at candidate would overlap
        # any other clip in the same track, then revert to original_candidate.
        for other in self.track_data.clips:
            if other is self.clip_data:
                continue
            if (
                candidate < other.start_frame + other.duration_frames
                and candidate + self.clip_data.duration_frames > other.start_frame
            ):
                candidate = original_candidate
                break

        # Update our clip's start_frame and reposition it.
        self.clip_data.start_frame = max(0, candidate)
        new_x_pos = (
            self.theme["LEFT_MARGIN"]
            + self.clip_data.start_frame
            * self.theme["BASE_PIXELS_PER_FRAME"]
            * view.h_zoom
        )
        self.setPos(new_x_pos, self._fixed_y)
        super().mouseReleaseEvent(event)

class TimelineView(QGraphicsView):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme

        # Use theme constants
        self.LEFT_MARGIN = theme["LEFT_MARGIN"]
        self.TOP_MARGIN = theme["TOP_MARGIN"]
        self.BOTTOM_MARGIN = theme["BOTTOM_MARGIN"]
        self.TRACK_SPACING = theme["TRACK_SPACING"]
        self.BASE_PIXELS_PER_FRAME = theme["BASE_PIXELS_PER_FRAME"]
        self.DEFAULT_TRACK_HEIGHT = theme["DEFAULT_TRACK_HEIGHT"]
        self.h_zoom = 1.0
        self.v_zoom = 1.0
        self.playhead_frame = 0
        self.end_frame = 0
        self.bottom_frame_offset = self.BOTTOM_MARGIN
        self.tracks = []  # list of TrackData
        self.scene_obj = QGraphicsScene()
        self.setScene(self.scene_obj)
        self.setRenderHint(QPainter.Antialiasing)

        # Create static items:
        self.timeLabelItem = TimeLabelItem(self.playhead_frame, theme=self.theme)
        self.scene_obj.addItem(self.timeLabelItem)
        self.rulerItem = RulerItem(theme=self.theme)
        self.scene_obj.addItem(self.rulerItem)
        self.playheadTriangleItem = PlayheadTriangleItem(self, theme=self.theme)
        self.scene_obj.addItem(self.playheadTriangleItem)
        self.playheadLineItem = PlayheadLineItem(self, theme=self.theme)
        self.scene_obj.addItem(self.playheadLineItem)
        self.endLineItem = EndLineItem(self, theme=self.theme)
        self.scene_obj.addItem(self.endLineItem)

        # Dynamic items:
        self.trackHeaderItems = []
        self.trackLaneItems = []
        self.clipItems = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.playbackStep)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setStyleSheet(f"background-color: {self.theme['background_color']};")
        self.updateLayout()

    def addTrack(self, track):
        self.tracks.append(track)
        self.updateLayout()

    def minimum_end_frame(self):
        max_end = 0
        for track in self.tracks:
            for clip in track.clips:
                end = clip.start_frame + clip.duration_frames
                if end > max_end:
                    max_end = end
        return max_end

    def updateLayout(self):
        scene_width = 2000
        y = self.TOP_MARGIN
        for track in self.tracks:
            y += track.height * self.v_zoom + self.TRACK_SPACING
        scene_height = y + self.bottom_frame_offset
        self.scene_obj.setSceneRect(0, 0, scene_width, scene_height)
        self.timeLabelItem.setPos(0, 0)
        self.timeLabelItem.update()
        self.rulerItem.setPos(self.LEFT_MARGIN, 0)
        self.rulerItem.update()
        ph_x = (
            self.LEFT_MARGIN
            + self.playhead_frame * self.BASE_PIXELS_PER_FRAME * self.h_zoom
        )
        self.playheadLineItem.setPos(ph_x, self.TOP_MARGIN)
        self.playheadLineItem.update()
        self.playheadTriangleItem.setPos(ph_x, 0)
        self.playheadTriangleItem.update()
        min_end = self.minimum_end_frame()
        self.end_frame = max(min_end + 24, 100)
        end_x = (
            self.LEFT_MARGIN 
            + self.end_frame 
            * self.BASE_PIXELS_PER_FRAME 
            * self.h_zoom
        )
        self.endLineItem.setPos(end_x, self.TOP_MARGIN)
        self.endLineItem.update()
        for item in self.trackHeaderItems:
            self.scene_obj.removeItem(item)
        self.trackHeaderItems = []
        for item in self.trackLaneItems:
            self.scene_obj.removeItem(item)
        self.trackLaneItems = []
        for item in self.clipItems:
            self.scene_obj.removeItem(item)
        self.clipItems = []
        current_y = self.TOP_MARGIN
        for track in self.tracks:
            header = TrackHeaderItem(track, theme=self.theme)
            header.setPos(0, current_y)
            self.scene_obj.addItem(header)
            self.trackHeaderItems.append(header)
            lane = TrackLaneItem(track, theme=self.theme)
            lane.setGeometry(
                self.LEFT_MARGIN,
                current_y,
                scene_width - self.LEFT_MARGIN,
                track.height * self.v_zoom,
            )
            self.scene_obj.addItem(lane)
            self.trackLaneItems.append(lane)
            for clip in track.clips:
                clip_x = (
                    self.LEFT_MARGIN
                    + clip.start_frame 
                    * self.BASE_PIXELS_PER_FRAME 
                    * self.h_zoom
                )
                clip_y = current_y
                clip_width = (
                    # to account for the clip's right edge being time inclusive
                    (clip.duration_frames * self.BASE_PIXELS_PER_FRAME)
                    + self.BASE_PIXELS_PER_FRAME
                ) * self.h_zoom
                clip_height = track.height * self.v_zoom
                clipItem = ClipItem(clip, track, theme=self.theme)
                clipItem.setGeometry(clip_x, clip_y, clip_width, clip_height)
                self.scene_obj.addItem(clipItem)
                self.clipItems.append(clipItem)
            current_y += track.height * self.v_zoom + self.TRACK_SPACING
        self.viewport().update()

    def setHZoom(self, value):
        self.h_zoom = 0.5 + (value / 100.0) * 3.5
        self.updateLayout()

    def setVZoom(self, value):
        self.v_zoom = 0.5 + (value / 100.0) * 1.5
        self.updateLayout()

    def updateFromPlayhead(self, new_frame):
        self.playhead_frame = int(round(new_frame))
        self.timeLabelItem.updateTime(self.playhead_frame)
        self.updateLayout()

    def setPlayheadFrame(self, frame):
        self.playhead_frame = frame
        self.timeLabelItem.updateTime(self.playhead_frame)
        self.updateLayout()

    def setEndFrame(self, frame):
        min_end = self.minimum_end_frame()
        if frame < min_end:
            frame = min_end
        self.end_frame = frame
        self.updateLayout()

    def playbackStep(self):
        self.playhead_frame += 1
        if self.playhead_frame >= self.end_frame:
            self.playhead_frame = 0
        self.updateFromPlayhead(self.playhead_frame)

    def startPlayback(self):
        interval = 1000 / 24
        self.timer.start(interval)

    def stopPlayback(self):
        self.timer.stop()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateLayout()


# --- Timeline Widget Container (with toolbar) ---
class TimelineWidget(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.theme = get_theme(config)
        # Override constants from theme

        for key in DEFAULT_CONSTANTS:
            if key in self.theme:
                globals()[key] = self.theme[key]
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # Toolbar at top:

        toolbar = QWidget()
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(5, 5, 5, 5)
        tb_layout.setSpacing(10)
        self.playButton = QPushButton("Play")
        self.playButton.clicked.connect(
            lambda: self.timeline_view.startPlayback()
        )
        self.stopButton = QPushButton("Stop")
        self.stopButton.clicked.connect(
            lambda: self.timeline_view.stopPlayback()
        )
        self.frameBackButton = QPushButton("<<")
        self.frameBackButton.clicked.connect(
            lambda: self.timeline_view.setPlayheadFrame(
                self.timeline_view.playhead_frame - 1
            )
        )
        self.frameForwardButton = QPushButton(">>")
        self.frameForwardButton.clicked.connect(
            lambda: self.timeline_view.setPlayheadFrame(
                self.timeline_view.playhead_frame + 1
            )
        )
        tb_layout.addWidget(self.playButton)
        tb_layout.addWidget(self.stopButton)
        tb_layout.addWidget(self.frameBackButton)
        tb_layout.addWidget(self.frameForwardButton)
        self.hZoomSlider = QSlider(Qt.Horizontal)
        self.hZoomSlider.setRange(1, 100)
        self.hZoomSlider.setValue(1)
        self.hZoomSlider.valueChanged.connect(
            lambda val: self.timeline_view.setHZoom(val)
        )
        self.vZoomSlider = QSlider(Qt.Horizontal)
        self.vZoomSlider.setRange(1, 100)
        self.vZoomSlider.setValue(50)
        self.vZoomSlider.valueChanged.connect(
            lambda val: self.timeline_view.setVZoom(val)
        )
        tb_layout.addWidget(QLabel("H-Zoom:"))
        tb_layout.addWidget(self.hZoomSlider)
        tb_layout.addWidget(QLabel("V-Zoom:"))
        tb_layout.addWidget(self.vZoomSlider)
        main_layout.addWidget(toolbar)
        self.timeline_view = TimelineView(self.theme)
        self.timeline_view.setHZoom(1)
        main_layout.addWidget(self.timeline_view)
        self.setStyleSheet(
            f"background-color: {self.theme['background_color']}; color: {self.theme['timeLabel_text']};"
        )

    def addTrack(self, track):
        self.timeline_view.addTrack(track)