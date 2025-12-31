import atexit
import argparse
import json
import os
import platform
import re
import signal
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from random import randint

import requests
from tqdm.auto import tqdm


CLOUDFLARED_CONFIG = {
    ("Windows", "AMD64"): {
        "command": "cloudflared-windows-amd64.exe",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
    },
    ("Windows", "x86"): {
        "command": "cloudflared-windows-386.exe",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-386.exe",
    },
    ("Linux", "x86_64"): {
        "command": "cloudflared-linux-amd64",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
    },
    ("Linux", "i386"): {
        "command": "cloudflared-linux-386",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-386",
    },
    ("Linux", "arm"): {
        "command": "cloudflared-linux-arm",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm",
    },
    ("Linux", "arm64"): {
        "command": "cloudflared-linux-arm64",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    },
    ("Linux", "aarch64"): {
        "command": "cloudflared-linux-arm64",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64",
    },
    ("Darwin", "x86_64"): {
        "command": "cloudflared",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz",
    },
    ("Darwin", "arm64"): {
        "command": "cloudflared",
        "url": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64.tgz",
    },
}


def _get_command(system: str, machine: str) -> str:
    try:
        return CLOUDFLARED_CONFIG[(system, machine)]["command"]
    except KeyError:
        raise Exception(f"{machine} is not supported on {system}")


def _get_url(system: str, machine: str) -> str:
    try:
        return CLOUDFLARED_CONFIG[(system, machine)]["url"]
    except KeyError:
        raise Exception(f"{machine} is not supported on {system}")


def _extract_tarball(tar_path: str, filename: str) -> None:
    tarfile_path = os.path.join(tar_path, filename)
    with tarfile.open(tarfile_path, "r") as tar:
        tar.extractall(tar_path)


def _download_file(url: str) -> str:
    local_filename = url.split("/")[-1]
    response = requests.get(url, stream=True)
    response.raise_for_status()

    download_path = str(Path(tempfile.gettempdir(), local_filename))

    with open(download_path, "wb") as f:
        file_size = int(response.headers.get("content-length", 50_000_000))
        chunk_size = 1024

        with tqdm(
            desc=" * Downloading",
            total=file_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as pbar:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    return download_path


def _download_cloudflared(cloudflared_path: str, command: str) -> None:
    system, machine = platform.system(), platform.machine()

    if Path(cloudflared_path, command).exists():
        executable = (
            os.path.join(cloudflared_path, "cloudflared")
            if (system == "Darwin" and machine in ["x86_64", "arm64"])
            else os.path.join(cloudflared_path, command)
        )

        subprocess.Popen(
            [executable, "update"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        return

    print(f" * Downloading cloudflared for {system} {machine}...")
    url = _get_url(system, machine)
    _download_file(url)


def handle_proxy(project_id: str, tunnel_url: str) -> None:
    worker_proxy_path = f"/tmp/{project_id}"

    if not os.path.exists(worker_proxy_path):
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(["cp", "-a", current_file_dir, worker_proxy_path], check=True)

    wrangler_jsonc = f"{worker_proxy_path}/wrangler.jsonc"

    with open(wrangler_jsonc, "r", encoding="utf-8") as f:
        wrangler_jsonc_data = json.load(f)

    wrangler_jsonc_data["vars"]["PROXY_URL"] = tunnel_url
    wrangler_jsonc_data["name"] = f"proxy_{project_id}"

    with open(wrangler_jsonc, "w", encoding="utf-8") as f:
        json.dump(wrangler_jsonc_data, f, indent=2)

    os.chdir(worker_proxy_path)
    print("deploy...")
    subprocess.run(["npm", "run", "deploy"], check=True)


def _run_cloudflared() -> None:
    parser = argparse.ArgumentParser(description="Run Cloudflared tunnel")

    parser.add_argument("-i", "--project_id", required=True)
    parser.add_argument("-p", "--port", type=int, required=True)
    parser.add_argument("-m", "--metrics_port", type=int)
    parser.add_argument("-t", "--tunnel_id")
    parser.add_argument("-c", "--config_path")
    parser.add_argument("-d", "--download", action="store_true")

    args = parser.parse_args()

    port = args.port
    project_id = args.project_id

    metrics_port = randint(8100, 9000) if args.metrics_port is None else args.metrics_port

    system, machine = platform.system(), platform.machine()
    command = _get_command(system, machine)

    cloudflared_path = tempfile.gettempdir()

    if system == "Darwin":
        _download_cloudflared(cloudflared_path, "cloudflared-darwin-amd64.tgz")
        _extract_tarball(cloudflared_path, "cloudflared-darwin-amd64.tgz")
    else:
        _download_cloudflared(cloudflared_path, command)

    executable = str(Path(cloudflared_path, command))
    os.chmod(executable, 0o777)

    print("[executable]", executable)

    if args.download:
        return

    cloudflared_command = [
        executable,
        "tunnel",
        "--metrics",
        f"127.0.0.1:{metrics_port}",
    ]

    if args.config_path:
        cloudflared_command += ["--config", args.config_path, "run"]
    elif args.tunnel_id:
        cloudflared_command += ["--url", f"http://127.0.0.1:{port}", "run", args.tunnel_id]
    else:
        cloudflared_command += ["--url", f"http://127.0.0.1:{port}"]

    if system == "Darwin" and machine == "arm64":
        cloudflared_command = ["arch", "-x86_64"] + cloudflared_command

    print("[cloudflared_command]", cloudflared_command)

    cloudflared = subprocess.Popen(
        cloudflared_command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    atexit.register(cloudflared.terminate)

    localhost_url = f"http://127.0.0.1:{metrics_port}/metrics"

    tunnel_url = None

    for _ in range(10):
        try:
            metrics = requests.get(localhost_url).text
            match = re.search(r"(?P<url>https?://[^\s]+\.trycloudflare\.com)", metrics)

            if match:
                tunnel_url = match.group("url")
                break

            time.sleep(3)
        except Exception:
            time.sleep(3)

    if not tunnel_url:
        raise Exception("Can't connect to Cloudflare Edge")

    handle_proxy(project_id, tunnel_url)

    print(f" * Running on {tunnel_url}")
    print(f" * Traffic stats at http://127.0.0.1:{metrics_port}/metrics")

    signal.pause()


def main():
    print(" * Starting Cloudflared tunnel...")
    _run_cloudflared()


if __name__ == "__main__":
    main()
