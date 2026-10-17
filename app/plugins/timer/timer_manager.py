"""计时器后台引擎 —— 2026-10-17 从 Lmn-copy ``ppt_assistant/core/timer_manager.py``
逐行移植（用户指令：HTML 版计时器原汁原味搬过来）。

为什么需要它：HTML 页面在窗口打开时自己跑倒计时（客户端 setInterval），但
窗口被用户关掉（实际是藏起来）后，恢复窗口时要从某个权威来源取回「还剩
多久、还在不在走」—— 这个线程里的 worker 就是那个权威来源。HTML 侧的
``get_timer_state`` / ``start_timer`` / ``update_timer`` 等桥接调用最终都
落到这里。

线程模型保持原版：``TimerWorker`` 活在专属 ``QThread`` 里，``TimerManager``
（单例）在主线程经信号转发控制与回报。页面只是藏起来时 WebEngine 照跑、
铃声照响，引擎更多是「重开窗口时的状态恢复源」与「宿主侧的可查询状态」。
"""

from PySide6.QtCore import QObject, QTimer, Signal, Slot, QThread


class TimerWorker(QObject):
    updated = Signal(int)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.timer = None
        self.total_seconds = 0.0
        self.remaining_seconds = 0.0
        self.is_running = False

    @Slot(int)
    def start(self, seconds):
        self.total_seconds = float(seconds)
        self.remaining_seconds = float(seconds)
        self.is_running = True
        if not self.timer:
            self.timer = QTimer(self)
            self.timer.setInterval(100)
            self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.updated.emit(int(self.remaining_seconds))

    @Slot()
    def pause(self):
        self.is_running = False
        if self.timer:
            self.timer.stop()

    @Slot()
    def resume(self):
        if self.remaining_seconds > 0:
            self.is_running = True
            if not self.timer:
                self.timer = QTimer(self)
                self.timer.setInterval(100)
                self.timer.timeout.connect(self._tick)
            self.timer.start()

    @Slot()
    def stop(self):
        self.remaining_seconds = 0.0
        self.is_running = False
        if self.timer:
            self.timer.stop()
        self.updated.emit(0)

    @Slot(int)
    def add_time(self, seconds):
        if self.remaining_seconds > 0 or self.is_running:
            self.remaining_seconds += float(seconds)
            if self.remaining_seconds < 0:
                self.remaining_seconds = 0
            self.updated.emit(int(self.remaining_seconds))

    @Slot(int)
    def update_time(self, total_seconds):
        self.remaining_seconds = float(total_seconds)
        self.updated.emit(int(self.remaining_seconds))

    def _tick(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 0.1
            if self.remaining_seconds <= 0:
                self.remaining_seconds = 0
                self.is_running = False
                if self.timer:
                    self.timer.stop()
                self.finished.emit()
            else:
                self.updated.emit(int(self.remaining_seconds))
        else:
            self.stop()


class TimerManager(QObject):
    updated = Signal(int)
    finished = Signal()
    state_changed = Signal(bool)  # is_running

    # 转发给 worker 线程的控制信号
    _request_start = Signal(int)
    _request_pause = Signal()
    _request_resume = Signal()
    _request_stop = Signal()
    _request_add_time = Signal(int)
    _request_update_time = Signal(int)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TimerManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True

        self._thread = QThread()
        self._worker = TimerWorker()
        self._worker.moveToThread(self._thread)
        self._thread.finished.connect(self._worker.deleteLater)

        self._request_start.connect(self._worker.start)
        self._request_pause.connect(self._worker.pause)
        self._request_resume.connect(self._worker.resume)
        self._request_stop.connect(self._worker.stop)
        self._request_add_time.connect(self._worker.add_time)
        self._request_update_time.connect(self._worker.update_time)

        self._worker.updated.connect(self.updated)
        self._worker.finished.connect(self.finished)

        self._thread.start()

    @property
    def remaining_seconds(self):
        # 跨线程读 float/bool：靠 GIL 足够（原版同款取舍）
        return self._worker.remaining_seconds

    @property
    def total_seconds(self):
        return self._worker.total_seconds

    @property
    def is_running(self):
        return self._worker.is_running

    @Slot(int)
    def start(self, seconds):
        self._request_start.emit(seconds)
        self.state_changed.emit(True)

    @Slot()
    def pause(self):
        self._request_pause.emit()
        self.state_changed.emit(False)

    @Slot()
    def resume(self):
        self._request_resume.emit()
        self.state_changed.emit(True)

    @Slot()
    def stop(self):
        self._request_stop.emit()
        self.state_changed.emit(False)

    @Slot(int)
    def add_time(self, seconds):
        self._request_add_time.emit(seconds)

    @Slot(int)
    def update_time(self, total_seconds):
        self._request_update_time.emit(total_seconds)

    @Slot()
    def finish(self):
        self.stop()
        self.finished.emit()

    def get_remaining_time_str(self):
        val = int(self.remaining_seconds)
        hours = val // 3600
        minutes = (val % 3600) // 60
        seconds = val % 60
        if hours > 0:
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        return f"{minutes:02}:{seconds:02}"

    def shutdown(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
