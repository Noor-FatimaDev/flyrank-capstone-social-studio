"""Start the whole system with one command:  python run.py

1. Creates the database tables if they are missing (safe to repeat).
2. Starts the API (uvicorn) and the worker (worker.py) as two separate
   processes. The worker can still be run and stopped on its own with
   `python worker.py`.
3. Ctrl+C stops both. If either one exits by itself, the other is stopped too.
"""

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))


def stop(procs):
    """Ask each process to stop, and force it if it does not."""
    for p in procs:
        if p.poll() is None:
            p.terminate()
    for p in procs:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


def main() -> int:
    os.chdir(ROOT) 
    py = sys.executable

    subprocess.run([py, "-m", "app.db.init_db"], check=True)

    names = ["api", "worker"]
    procs = [
        subprocess.Popen([py, "-m", "uvicorn", "app.main:app"]),
        subprocess.Popen([py, "worker.py"]),
    ]
    try:
        while True:
            for name, p in zip(names, procs):
                if p.poll() is not None:
                    print(f"run.py: {name} exited with code {p.returncode}; stopping the rest")
                    return p.returncode or 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("run.py: stopping")
        return 0
    finally:
        stop(procs)


if __name__ == "__main__":
    sys.exit(main())