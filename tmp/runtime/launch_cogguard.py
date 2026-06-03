import os
import subprocess
import time
from pathlib import Path

ROOT = Path(r"G:\CISCN\cogguard_system")
RUNTIME = ROOT / "tmp" / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)
BACKEND = ROOT / "new-system" / "backend"
FRONTEND = ROOT / "new-system" / "frontend"
PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
NPM = Path(r"D:\node\npm.cmd")

ENV = {
    "PATH": r"D:\node;G:\CISCN\cogguard_system\new-system\backend\.venv\Scripts;C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0",
    "SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"),
    "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
    "TEMP": os.environ.get("TEMP", str(RUNTIME)),
    "TMP": os.environ.get("TMP", str(RUNTIME)),
    "USERPROFILE": os.environ.get("USERPROFILE", r"C:\Users\p"),
    "APPDATA": os.environ.get("APPDATA", r"C:\Users\p\AppData\Roaming"),
    "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", r"C:\Users\p\AppData\Local"),
    "HOMEDRIVE": os.environ.get("HOMEDRIVE", "C:"),
    "HOMEPATH": os.environ.get("HOMEPATH", r"\\Users\\p"),
    "USERNAME": os.environ.get("USERNAME", "p"),
    "USER": os.environ.get("USER", "p"),
    "LOGNAME": os.environ.get("LOGNAME", "p"),
}

CREATE_FLAGS = 0
if os.name == "nt":
    CREATE_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP


def start(name, args, cwd):
    out = open(RUNTIME / f"{name}.out.log", "ab", buffering=0)
    err = open(RUNTIME / f"{name}.err.log", "ab", buffering=0)
    p = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=ENV,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=err,
        creationflags=CREATE_FLAGS,
    )
    return p, out, err

backend, backend_out, backend_err = start(
    "backend",
    [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "info"],
    BACKEND,
)
frontend, frontend_out, frontend_err = start(
    "frontend",
    [str(NPM), "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
    FRONTEND,
)

(RUNTIME / "cogguard-pids.txt").write_text(
    f"supervisor={os.getpid()}\nbackend={backend.pid}\nfrontend={frontend.pid}\n",
    encoding="utf-8",
)

try:
    while True:
        status = [
            f"supervisor={os.getpid()}",
            f"backend={backend.pid} rc={backend.poll()}",
            f"frontend={frontend.pid} rc={frontend.poll()}",
            f"updated={time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        (RUNTIME / "cogguard-status.txt").write_text("\n".join(status) + "\n", encoding="utf-8")
        time.sleep(3)
finally:
    for p in (backend, frontend):
        if p.poll() is None:
            p.terminate()
    backend_out.close(); backend_err.close(); frontend_out.close(); frontend_err.close()

