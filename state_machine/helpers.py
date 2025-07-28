import logging
from datetime import datetime

class PerformanceMetrics:
    def __init__(self):
        self.frame_start = None
        self.frame_end   = None
        self.frame_in_progress = False
        self.buffer_size = 1000
        self.total_frames = 0

        self.frame_time_buffer = []
        self.global_max_frame_time = 0
        self.global_min_frame_time = 0

    def register_frame_start(self):
        if self.frame_in_progress:
            logging.warning(f"Frame already in progress")
            return
        self.frame_in_progress = True
        self.frame_start = datetime.now()

    def register_frame_end(self):
        if not self.frame_start:
            logging.warning(f"Frame not started")
            return
        self.frame_in_progress = False
        self.frame_end = datetime.now()
        self.frame_time_buffer.append(self.frame_end - self.frame_start)
        self.total_frames += 1

        if len(self.frame_time_buffer) > self.buffer_size:
            self.frame_time_buffer.pop(0)

    def get_metrics(self):
        if not self.frame_time_buffer:
            return None

        total_time = sum((ft.total_seconds() for ft in self.frame_time_buffer), 0.0)
        return {
            "average_frame_time": total_time / len(self.frame_time_buffer),
            "max_frame_time": max(self.frame_time_buffer, key=lambda x: x.total_seconds()).total_seconds(),
            "min_frame_time": min(self.frame_time_buffer, key=lambda x: x.total_seconds()).total_seconds(),
            "total_frames": self.total_frames
        }
    

class LoggerUtils:

    HR  = "-" * 64
    SHR = "*" * 64

    def pretty_format_args(kwargs):
        text = "Kwargs:\n"
        text += "\n".join([f"\t{k}: {v}" for k, v in kwargs.items()])
        return text
    

