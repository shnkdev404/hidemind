"""Start (or restart) a local Hindsight container using the Groq key from .env.

Usage: python scripts/start_hindsight.py [--recreate]
Memory data persists in the Docker volume 'hindsight-data' across restarts.
"""

import argparse
import subprocess
import sys
import time
import urllib.request

import _common  # noqa: F401

from app.config import get_settings

NAME = "hindsight"
IMAGE = "ghcr.io/vectorize-io/hindsight:latest"


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def healthy(url: str) -> bool:
    for path in ("/health", "/v1/default/banks", "/docs"):
        try:
            with urllib.request.urlopen(url + path, timeout=3) as r:
                if r.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def main(recreate: bool) -> None:
    s = get_settings()
    if not s.groq_api_key:
        sys.exit("GROQ_API_KEY is empty in .env - add your key (https://console.groq.com/keys) and re-run.")
    if docker("info", check=False).returncode != 0:
        sys.exit("Docker daemon is not running - start Docker Desktop and re-run.")

    exists = docker("ps", "-a", "--filter", f"name=^{NAME}$", "--format", "{{.Names}}").stdout.strip() == NAME
    if exists and recreate:
        docker("rm", "-f", NAME)
        exists = False
    if exists:
        docker("start", NAME)
        print("Started existing container 'hindsight'.")
    else:
        docker("run", "-d", "--name", NAME, "--restart", "unless-stopped", "--shm-size=1g",
               "-p", "8888:8888", "-p", "9999:9999",
               "-e", "HINDSIGHT_API_LLM_PROVIDER=groq",
               "-e", f"HINDSIGHT_API_LLM_API_KEY={s.groq_api_key}",
               "-e", "HINDSIGHT_API_LLM_MODEL=openai/gpt-oss-20b",
               "-e", "HINDSIGHT_API_LLM_GROQ_SERVICE_TIER=on_demand",
               "-e", "HINDSIGHT_API_WORKER_ID=munshi-local",
               "-v", "hindsight-data:/home/hindsight/.pg0", IMAGE)
        print("Created container 'hindsight'.")

    print("Waiting for the API on http://localhost:8888 ...", end="", flush=True)
    for _ in range(90):
        if healthy("http://localhost:8888"):
            print(" ready.\nAPI: http://localhost:8888  ·  Control plane: http://localhost:9999")
            return
        print(".", end="", flush=True)
        time.sleep(2)
    print("\nNot healthy after 3 minutes. Logs:\n" + docker("logs", "--tail", "40", NAME, check=False).stdout)
    sys.exit(1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recreate", action="store_true")
    main(ap.parse_args().recreate)
