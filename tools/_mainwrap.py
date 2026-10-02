import sys, os, traceback
log_path = os.path.join(os.path.dirname(sys.executable), "_crash.log")
try:
    import main
    if __name__ == "__main__":
        raise SystemExit(main.main())
except SystemExit as e:
    raise
except Exception:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    print(traceback.format_exc())
    raise
