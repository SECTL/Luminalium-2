import sys
from pathlib import Path
p = Path(sys.executable).resolve().parent / "_hello.log"
with open(p, "w", encoding="utf-8") as f:
    f.write("hello from frozen script\n")
    f.write(f"executable={sys.executable}\n")
    f.write(f"frozen={getattr(sys,'frozen',None)}\n")
