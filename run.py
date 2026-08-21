"""
TeXa Single-Command Launcher
Runs FastAPI Backend and serves TeXa web application locally at http://localhost:8000
"""

import os
import sys
import socket
import subprocess
import webbrowser
import time
import threading

def free_port(port=8000):
    """Check if port is in use and terminate lingering process on macOS/Linux."""
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        pids = result.stdout.strip().split()
        for pid in pids:
            if pid and pid.isdigit():
                print(f"[*] Port {port} is occupied by PID {pid}. Cleaning up existing process...")
                subprocess.run(["kill", "-9", pid], capture_output=True)
                time.sleep(0.5)
    except Exception:
        pass

def ensure_frontend_build(base_dir):
    """Ensures frontend dist/index.html exists; builds it if missing."""
    frontend_dir = os.path.join(base_dir, "frontend")
    dist_index = os.path.join(frontend_dir, "dist", "index.html")
    if not os.path.exists(dist_index):
        print("[*] Frontend distribution build not found. Building web assets with Vite...")
        try:
            npm_cmd = "npm.cmd" if sys.platform.startswith("win") else "npm"
            subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, check=True, shell=sys.platform.startswith("win"))
            print("[*] Frontend built successfully.")
        except Exception as build_err:
            print(f"[!] Warning: Frontend build encountered an issue: {build_err}")

def wait_and_open_browser(port=8000):
    """Polls backend port until active before opening web browser."""
    url = f"http://127.0.0.1:{port}"
    max_attempts = 50
    for _ in range(max_attempts):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                time.sleep(0.3)
                webbrowser.open(url)
                return
        except (OSError, ConnectionRefusedError):
            time.sleep(0.2)
    # Fallback open
    webbrowser.open(url)

def main():
    print("=" * 60)
    print("             TeXa - Minimalist AI LaTeX Editor")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Locate virtual environment Python across macOS, Linux, and Windows
    posix_python = os.path.join(base_dir, "venv", "bin", "python")
    win_python = os.path.join(base_dir, "venv", "Scripts", "python.exe")
    
    if os.path.exists(posix_python):
        venv_python = posix_python
    elif os.path.exists(win_python):
        venv_python = win_python
    else:
        venv_python = sys.executable

    port = 8000
    free_port(port)
    ensure_frontend_build(base_dir)

    print(f"[*] Starting TeXa backend using Python: {venv_python}")
    print(f"[*] Launching web app server on http://localhost:{port} ...")

    # Automatically open web browser only after the server is actively listening
    threading.Thread(target=wait_and_open_browser, args=(port,), daemon=True).start()

    # Launch Uvicorn FastAPI server
    try:
        subprocess.run([
            venv_python, "-m", "uvicorn", "backend.main:app",
            "--host", "127.0.0.1",
            "--port", str(port)
        ], cwd=base_dir)
    except KeyboardInterrupt:
        print("\n[!] TeXa server stopped.")

if __name__ == "__main__":
    main()


