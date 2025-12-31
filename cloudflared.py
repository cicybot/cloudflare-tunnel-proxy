import atexit
import requests
import subprocess
import tarfile
import tempfile
import shutil
import os
import platform
import time
import re
from random import randint
from threading import Timer
from pathlib import Path
from tqdm.auto import tqdm
import threading
import signal
import argparse
import json


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


def _get_command(system, machine):
    try:
        return CLOUDFLARED_CONFIG[(system, machine)]["command"]
    except KeyError:
        raise Exception(f"{machine} is not supported on {system}")


def _get_url(system, machine):
    try:
        return CLOUDFLARED_CONFIG[(system, machine)]["url"]
    except KeyError:
        raise Exception(f"{machine} is not supported on {system}")


# Needed for the darwin package
def _extract_tarball(tar_path, filename):
    tar = tarfile.open(tar_path + "/" + filename, "r")
    for item in tar:
        tar.extract(item, tar_path)
        if item.name.find(".tgz") != -1 or item.name.find(".tar") != -1:
            extract(item.name, "./" + item.name[: item.name.rfind("/")])


def extract(filename, path):
    tar = tarfile.open(filename, "r")
    for item in tar:
        tar.extract(item, path)
        if item.name.find(".tgz") != -1 or item.name.find(".tar") != -1:
            extract(item.name, "./" + item.name[: item.name.rfind("/")])


def _download_cloudflared(cloudflared_path, command):
    system, machine = platform.system(), platform.machine()
    if Path(cloudflared_path, command).exists():
        executable = (
            (cloudflared_path + "/" + "cloudflared")
            if (system == "Darwin" and machine in ["x86_64", "arm64"])
            else (cloudflared_path + "/" + command)
        )
        update_cloudflared = subprocess.Popen(
            [executable, "update"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        )
        return
    print(f" * Downloading cloudflared for {system} {machine}...")
    url = _get_url(system, machine)
    _download_file(url)


def _download_file(url):
    local_filename = url.split("/")[-1]
    r = requests.get(url, stream=True)
    r.raise_for_status()
    download_path = str(Path(tempfile.gettempdir(), local_filename))
    with open(download_path, "wb") as f:
        file_size = int(r.headers.get("content-length", 50000000))  # type: ignore
        chunk_size = 1024
        with tqdm(
                desc=" * Downloading",
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
        ) as pbar:
            for chunk in r.iter_content(chunk_size=chunk_size):
                f.write(chunk)
                pbar.update(chunk_size)
    return download_path

def _run_cloudflared():

    parser = argparse.ArgumentParser(description="Run Cloudflared tunnel")

    # Define options
    parser.add_argument('-i', '--project_id', type=str, help='the project_id for the tunnel',required=True)
    parser.add_argument('-p', '--port', type=int, help='the port to tunnel',required=True)
    parser.add_argument('-m', '--metrics_port', type=int, help='the metrics port to tunnel')
    parser.add_argument('-t', '--tunnel_id', type=int, help='the tunnel id to tunnel')
    parser.add_argument('-c', '--config_path', type=int, help='the config path to tunnel')
	parser.add_argument('-d', '--download', type=int, help='download cloudflared')
    # parser.add_argument('-o', '--token', type=int, help='the token to tunnel')

    # Parse arguments
    args = parser.parse_args()
    port = args.port
    project_id = args.project_id
    project_id = args.download


    metrics_port =  randint(8100, 9000) if args.metrics_port is None else args.metrics_port

    tunnel_id = args.tunnel_id
    config_path = args.config_path
    system, machine = platform.system(), platform.machine()
    command = _get_command(system, machine)
    cloudflared_path = str(Path(tempfile.gettempdir()))
    if system == "Darwin":
        _download_cloudflared(cloudflared_path, "cloudflared-darwin-amd64.tgz")
        _extract_tarball(cloudflared_path, "cloudflared-darwin-amd64.tgz")
    else:
        _download_cloudflared(cloudflared_path, command)

    executable = str(Path(cloudflared_path, command))
    os.chmod(executable, 0o777)
	
	if download is not None:
		return

    cloudflared_command = [
        executable,
        "tunnel","--metrics",
        f"127.0.0.1:{metrics_port}",
    ]
    if config_path:
        cloudflared_command += ["--config", config_path, "run"]
    elif tunnel_id:
        cloudflared_command += ["--url", f"http://127.0.0.1:{port}", "run", tunnel_id]
    else:
        cloudflared_command += ["--url", f"http://127.0.0.1:{port}"]

    if system == "Darwin" and machine == "arm64":
        cloudflared_command = ["arch", "-x86_64"] + cloudflared_command
    print("[cloudflared_command]",cloudflared_command)
    # if token is None and os.getenv("CLOUDFLARED_TOKEN") is not None:
    #     token = os.getenv("CLOUDFLARED_TOKEN")
    # if token is not None:
    #     cloudflared_command += ["--token", token]
    #     print("[token]",token[0:10])
    cloudflared = subprocess.Popen(
        cloudflared_command, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
    )

    atexit.register(cloudflared.terminate)
    localhost_url = f"http://127.0.0.1:{metrics_port}/metrics"

    for _ in range(10):
        try:
            metrics = requests.get(localhost_url).text
            if tunnel_id or config_path:
                # If tunnel_id or config_path is provided, we check for cloudflared_tunnel_ha_connections, as no tunnel URL is available in the metrics
                if re.search(r"cloudflared_tunnel_ha_connections\s\d", metrics):
                    # No tunnel URL is available in the metrics, so we return a generic text
                    tunnel_url = "preconfigured tunnel URL"
                    break
            else:
                # If neither tunnel_id nor config_path is provided, we check for the tunnel URL in the metrics
                tunnel_url = re.search(
                    r"(?P<url>https?:\/\/[^\s]+.trycloudflare.com)", metrics
                )
                if tunnel_url:
                    tunnel_url = tunnel_url.group("url")
                break
        except:
            time.sleep(3)
    else:
        raise Exception(f"! Can't connect to Cloudflare Edge")

    handle_proxy(project_id,tunnel_url)
    print(f" * Running on {tunnel_url}")
    print(f" * Traffic stats available on http://127.0.0.1:{metrics_port}/metrics")


def handle_proxy(project_id,tunnel_url):
    worker_proxy_path = f"/tmp/{project_id}"

    if not os.path.exists(worker_proxy_path):
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(
            ["cp", "-a",current_file_dir,worker_proxy_path],check=True
        )

    wrangler_jsonc = f"{worker_proxy_path}/wrangler.jsonc"

    # 1) read file
    with open(wrangler_jsonc, "r", encoding="utf-8") as f:
        content = f.read()

    # 3) parse json
    wrangler_jsonc_data = json.loads(content)

    # 4) modify PROXY_URL
    wrangler_jsonc_data['vars']["PROXY_URL"] = tunnel_url
    wrangler_jsonc_data['name'] = "proxt_"+project_id

    # 5) write back as JSONC-compatible text (pretty JSON)
    with open(wrangler_jsonc, "w", encoding="utf-8") as f:
        json.dump(wrangler_jsonc_data, f, indent=2)
    os.chdir(worker_proxy_path)
    print("deploy...")
    subprocess.run(
        ["npm","run","deploy"],check=True
    )

def main():
    print(" * Starting Cloudflared tunnel...")
    _run_cloudflared()
    signal.pause()  # blocks forever

main()
