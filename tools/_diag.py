import sys, traceback, os
log_path = os.path.join(os.path.dirname(sys.executable), "_diag.log")

def w(msg):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

w(f"=== diag start, frozen={getattr(sys,'frozen',False)}, MEIPASS={getattr(sys,'_MEIPASS','N/A')}")
w(f"sys.executable={sys.executable}")
w(f"cwd={os.getcwd()}")
w(f"sys.path={sys.path}")

try:
    import PySide6
    w("PySide6 OK")
    from PySide6.QtCore import QCoreApplication
    w("QtCore OK")
    from PySide6.QtGui import QGuiApplication
    w("QtGui OK")
    from PySide6.QtWidgets import QApplication
    w("QtWidgets OK")
    from PySide6.QtQml import QQmlApplicationEngine
    w("QtQml OK")
    from PySide6.QtQuick import QQuickWindow
    w("QtQuick OK")
except Exception:
    w("QT IMPORT FAIL:/n" + traceback.format_exc())

try:
    import RinUI
    w(f"RinUI OK file={RinUI.__file__}")
    from RinUI import RinUIWindow, Theme, BackdropEffect
    w("RinUIWindow OK")
    from RinUI.core.config import RINUI_PATH
    w(f"RINUI_PATH={RINUI_PATH} exists={RINUI_PATH.exists()} qmldir={(RINUI_PATH/'RinUI'/'qmldir').exists()}")
except Exception:
    w("RINUI IMPORT FAIL:/n" + traceback.format_exc())

try:
    import win32api, win32con, win32gui
    w("pywin32 OK")
except Exception:
    w("PYWIN32 FAIL:/n" + traceback.format_exc())

try:
    import pythoncom
    w("pythoncom OK")
except Exception:
    w("PYTHONCOM FAIL:/n" + traceback.format_exc())

try:
    from app.application import main
    w("app.application import OK")
except Exception:
    w("APP IMPORT FAIL:/n" + traceback.format_exc())

w("=== diag end")
