"""Build one Flutter image for one architecture, check it, and push it.

Usage: python tools/build.py PLATFORM ARCH --rev SHA --engine HASH --tree DIR --out DIR [--base IMAGE] [--push]

PLATFORM is web, linux or windows; ARCH is amd64 or arm64. The engine's files come from the release
`engine-<ENGINE>` of Boriken-Dev/flutter: they are fetched into --tree (each checked against the release's SHA-256
manifest) and served on this machine, and the build reaches them through that server only. Then the image runs
`flutter --version` and builds a sample app with the storage address set to a dead port, so a fetch from outside
fails the run. The Flutter version is written to --out/version.txt for the manifest job.
"""
import argparse
import json
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = "ghcr.io/boriken-dev"
PORT = 8765
DEAD = "http://127.0.0.1:9"
DEBIAN = "debian:13.7-slim"

# A plain `flutter create` app per platform, built inside the finished image.
SMOKE = {
    "web": "set -o pipefail; cd /tmp && flutter create smoke_app >/dev/null && cd smoke_app && flutter build web 2>&1 | tail -n 8 && ls build/web",
    "linux": "set -o pipefail; cd /tmp && flutter create smoke_app >/dev/null && cd smoke_app && flutter build linux 2>&1 | tail -n 8 && ls build/linux",
    # flutter writes notices to stderr; as error records they would end the script, so the preference is Continue and
    # the verdict is flutter's exit code.
    "windows": "$ErrorActionPreference = 'Continue'; Set-Location $env:USERPROFILE; flutter create smoke_app | Out-Null; "
               "Set-Location smoke_app; flutter build windows 2>&1 | ForEach-Object { [string]$_ } | Select-Object -Last 8; "
               "if ($LASTEXITCODE -ne 0) { exit 1 }",
}


def run(cmd, **kw):
    print("+ " + " ".join(map(str, cmd))[:400], flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit(f"build: {cmd[0]} {cmd[1]} failed ({r.returncode})")
    return r


def out(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("platform", choices=("web", "linux", "windows"))
    ap.add_argument("arch", choices=("amd64", "arm64"))
    ap.add_argument("--rev", required=True, help="the mirror commit, 40 hex")
    ap.add_argument("--engine", required=True)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", default="", help="the image to build on; empty builds the Containerfile's Debian toolchain stage")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()

    win = a.platform == "windows"
    short = a.rev[:10]
    name = f"{REGISTRY}/flutter-{a.platform}"
    tag = f"{name}:{short}-{a.arch}"
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    log = outdir / "served.log"
    log.unlink(missing_ok=True)

    run([sys.executable, str(ROOT / "tools" / "flutter_artifacts.py"), "fetch-tree", a.tree, a.engine])
    bind = "0.0.0.0" if win else "127.0.0.1"
    srv = subprocess.Popen([sys.executable, str(ROOT / "tools" / "flutter_artifacts.py"), "serve", "--offline", "--dir", a.tree,
                            "--log", str(log), "--bind", bind, "--port", str(PORT)], stdout=subprocess.PIPE, text=True)
    threading.Thread(target=lambda: [print("  serve: " + l.rstrip(), flush=True) for l in srv.stdout], daemon=True).start()
    try:
        # A Windows container reaches this machine through the gateway of the NAT network; a Linux build shares the host's.
        host = "127.0.0.1"
        if win:
            host = out(["docker", "network", "inspect", "nat", "--format", "{{(index .IPAM.Config 0).Gateway}}"])
            if not host:
                sys.exit("build: no gateway on the docker network nat")
        storage = f"http://{host}:{PORT}"
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", PORT), timeout=1).close()
                break
            except OSError:
                if srv.poll() is not None:
                    sys.exit("build: the artifact server exited")
                time.sleep(0.2)
        else:
            sys.exit("build: the artifact server did not start")
        base = a.base or f"{DEBIAN} (toolchain of the Containerfile)"
        desc = (f"Flutter SDK from Boriken-Dev/flutter at {short}, engine {a.engine[:12]} from its release "
                f"engine-{a.engine[:12]}, on {base.split('@')[0]}")
        cmd = ["docker", "build", "-f", str(ROOT / "containers" / f"Containerfile.{a.platform}"), "-t", tag,
               "--build-arg", "MIRROR_URL=https://github.com/Boriken-Dev/flutter.git", "--build-arg", f"MIRROR_REV={a.rev}",
               "--build-arg", f"FLUTTER_STORAGE_BASE_URL={storage}", "--build-arg", f"IMAGE_DESCRIPTION={desc}",
               "--build-arg", f"BASE_NAME={base}"]
        if a.base:
            cmd += ["--build-arg", f"BASE={a.base}"]
        if win:
            cmd += ["--isolation=process"]
        else:
            cmd += ["--network=host"]
        cmd.append(str(ROOT / "containers"))
        t0 = time.time()
        run(cmd)
        print(f"build: {tag} built in {time.time() - t0:.0f}s", flush=True)

        runflags = ["--rm", "-e", f"FLUTTER_STORAGE_BASE_URL={DEAD}"] + (["--isolation=process"] if win else ["--network=host"])
        shell = ["powershell", "-NoProfile", "-Command"] if win else ["bash", "-c"]
        ver = subprocess.run(["docker", "run", *runflags, tag, *shell, "flutter --version --machine"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            info = json.loads(ver.stdout[ver.stdout.index("{"):ver.stdout.rindex("}") + 1])
        except ValueError:
            sys.exit(f"build: flutter --version in {tag}:\n{ver.stdout[-800:]}{ver.stderr[-800:]}")
        size = out(["docker", "image", "inspect", tag, "--format", "{{.Size}}"])
        print(f"build: flutter {info.get('frameworkVersion')} engine {info.get('engineContentHash')} "
              f"dart {info.get('dartSdkVersion')} size {size} bytes", flush=True)
        if info.get("engineContentHash") != a.engine:
            sys.exit(f"build: the image reports engine {info.get('engineContentHash')}, not {a.engine}")
        (outdir / "version.txt").write_text(info["frameworkVersion"], encoding="utf-8", newline="\n")
        (outdir / "size.txt").write_text(size, encoding="utf-8", newline="\n")

        t0 = time.time()
        run(["docker", "run", *runflags, tag, *shell, SMOKE[a.platform]])
        print(f"build: sample app built in {time.time() - t0:.0f}s", flush=True)

        rows = [l.split("\t") for l in log.read_text(encoding="utf-8").splitlines() if l] if log.exists() else []
        misses = [r[3] for r in rows if r[0] == "MISS"]
        print(f"build: served tree {len(rows)} requests, {len({r[3] for r in rows})} distinct paths, {len(misses)} missed")
        if misses:
            sys.exit("build: a request missed the served tree: " + ", ".join(misses[:10]))
    finally:
        srv.terminate()

    if a.push:
        run(["docker", "push", tag])
        if win:
            # One architecture: no index to join, so the final tags are this image.
            for t in (short, info["frameworkVersion"]):
                run(["docker", "tag", tag, f"{name}:{t}"])
                run(["docker", "push", f"{name}:{t}"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
