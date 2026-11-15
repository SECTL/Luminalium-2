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

2026-10-18 追加（plugin-audit F2/F15）：``finished`` 从「无人订阅的孤信号」
升格为到点提醒的 Python 权威（页面 setInterval 藏窗后会被 Chromium 节流，
铃声不能押在它身上 —— 订阅与露面在 plugin.py）；``is_finished`` 记住
「到过了」的结束态，``get_timer_state`` 能查，重开窗口恢复铃铛页。
"""

from PySide6.QtCore import QObject, QTimer, Signal, Slot, QThread

import time


class TimerWorker(QObject):
    updated = Signal(int)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.timer = None
        self.total_seconds = 0.0
        self.remaining_seconds = 0.0
        self.is_running = False
        # 墙钟截止时刻（time.time() 纪元秒；2026-10-18 plugin-audit F7）：
        # interval 逐拍递减在系统睡眠后从睡前剩余继续走（铃声响在 15:20
        # 而不是 15:00）。_tick 改以 deadline 现算剩余 —— 睡眠唤醒即补算、
        # 到点即发；「到 HH:MM 响铃」的目标时刻模式本来就是墙钟语义。
        self._deadline: float | None = None

    @Slot(int)
    def start(self, seconds):
        self.total_seconds = float(seconds)
        self.remaining_seconds = float(seconds)
        self.is_running = True
        self._deadline = time.time() + float(seconds)
        if not self.timer:
            self.timer = QTimer(self)
            self.timer.setInterval(100)
            self.timer.timeout.connect(self._tick)
        self.timer.start()
        self.updated.emit(int(self.remaining_seconds))

    @Slot()
    def pause(self):
        # 冻结在暂停瞬间（墙钟语义下剩余平时由 deadline 现算，拍间有
        # ≤100ms 的账面滞后，暂停这一下把它算准）
        if self._deadline is not None:
            self.remaining_seconds = max(0.0, self._deadline - time.time())
        self.is_running = False
        if self.timer:
            self.timer.stop()

    @Slot()
    def resume(self):
        if self.remaining_seconds > 0:
            self.is_running = True
            self._deadline = time.time() + self.remaining_seconds
            if not self.timer:
                self.timer = QTimer(self)
                self.timer.setInterval(100)
                self.timer.timeout.connect(self._tick)
            self.timer.start()

    @Slot()
    def stop(self):
        self.remaining_seconds = 0.0
        self.is_running = False
        self._deadline = None
        if self.timer:
            self.timer.stop()
        self.updated.emit(0)

    @Slot(int)
    def add_time(self, seconds):
        if self.remaining_seconds > 0 or self.is_running:
            before = self.remaining_seconds
            self.remaining_seconds = max(0.0, before + float(seconds))
            # 加时同步总数（2026-10-18 plugin-audit F16）：total 只涨实际
            # 到账的剩余增量（负加时把剩余钳到 0 时不虚减），重开窗口的
            # 圆环才不会按旧总数算出溢出
            self.total_seconds = max(
                0.0, self.total_seconds + (self.remaining_seconds - before)
            )
            if self._deadline is not None:
                self._deadline += self.remaining_seconds - before
            self.updated.emit(int(self.remaining_seconds))

    @Slot(int)
    def update_time(self, total_seconds):
        self.remaining_seconds = float(total_seconds)
        self._deadline = time.time() + float(total_seconds)
        self.updated.emit(int(self.remaining_seconds))

    def _tick(self):
        if self._deadline is not None:
            # 墙钟语义：剩余以 deadline 现算（睡眠唤醒即补算），到点即发
            self.remaining_seconds = self._deadline - time.time()
            if self.remaining_seconds <= 0:
                self.remaining_seconds = 0
                self.is_running = False
                if self.timer:
                    self.timer.stop()
                self.finished.emit()
            else:
                self.updated.emit(int(self.remaining_seconds))
        elif self.remaining_seconds > 0:
            # 无 deadline（外部 update_time 旧路径兜底）：退回逐拍递减
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
        # worker 自然到点先记结束态再转发（页面收尾路径 finish() 同记一个
        # 结束态；两路几乎同时发生时 finished 可能双发，订阅方有 latch）
        self._worker.finished.connect(self._on_worker_finished)
        self._is_finished = False

        self._thread.start()

    def _on_worker_finished(self):
        self._is_finished = True
        self.finished.emit()

    @property
    def is_finished(self):
        """「时间到」结束态：到过点为 True，start / stop（重置）清掉。"""
        return self._is_finished

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
        self._is_finished = False
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
        self._is_finished = False
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
        # 页面收尾路径（finishCountdown → finish_timer）：记结束态 + 停表 +
        # 发 finished，与 worker 自然到点（_on_worker_finished）同账 —— 原版
        # 这里调 self.stop()，会把结束态当场清掉，故停表三件事展开写
        self._is_finished = True
        self._request_stop.emit()
        self.state_changed.emit(False)
        self.finished.emit()

    def shutdown(self):
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
