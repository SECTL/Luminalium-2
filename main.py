"""诊断版 v3 —— 从最开头就开始记录。"""
import sys, os, traceback
from pathlib import Path

CRASH = Path(sys.executable).resolve().parent / "_crash.log"
def log(msg):
    try:
        with open(CRASH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass

log("=== script started")
log(f"executable={sys.executable}")
log(f"argv={sys.argv}")
log(f"frozen={getattr(sys,'frozen',None)} meipass={getattr(sys,'_MEIPASS',None)}")
log(f"cwd_before={os.getcwd()}")
log(f"sys.path={sys.path}")

try:
    ROOT = Path(__file__).resolve().parent
    log(f"ROOT={ROOT}")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    log(f"cwd_after={os.getcwd()}")
    from app.application import main
    log("import main OK")
    if __name__ == "__main__":
        log("calling main()")
        raise SystemExit(main())
except SystemExit as e:
    log(f"SystemExit {e}")
    raise
except BaseException:
    log("EXCEPTION:/n" + traceback.format_exc())
    raise
