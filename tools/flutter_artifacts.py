"""Mirror the engine artifacts of one Flutter engine as release assets of Boriken-Dev/flutter.

Usage:
    $AGENTS_PYTHON -I ~/.agents/tools/flutter_artifacts.py list     ENGINE [--rev REV] [--platforms P,...]
    $AGENTS_PYTHON -I ~/.agents/tools/flutter_artifacts.py publish  ENGINE [--rev REV] [--platforms P,...]
        [--target OWNER/REPO] [--work DIR] [--keep] [--dry-run]
    $AGENTS_PYTHON -I ~/.agents/tools/flutter_artifacts.py fetch-tree DIR ENGINE... [--target OWNER/REPO]
    $AGENTS_PYTHON -I ~/.agents/tools/flutter_artifacts.py serve ENGINE... [--port N] [--bind ADDR] [--dir DIR]
        [--target OWNER/REPO] [--log FILE] [--offline]

ENGINE is the 40-hex engine hash (the mirror's bin/internal/engine.version). REV is the
mirror commit whose bin/internal/{material_fonts,gradle_wrapper}.version name the fonts and the
Gradle wrapper (default: the mirror's `main`). P is a comma list of `windows-x64`,
`windows-arm64`, `linux-x64`, `linux-arm64` (the default is all four); `web` and the
platform-independent files are always included.

What it holds: everything `flutter precache --web --windows --linux` (universal artifacts
included), the Dart SDK of each host (`bin/internal/update_dart_sdk.{sh,ps1}`) and the first
`flutter build web|windows|linux` and `flutter test` fetch from FLUTTER_STORAGE_BASE_URL. The list
was measured against a logging proxy on Windows arm64 and Fedora arm64 and agrees with
packages/flutter_tools/lib/src/{flutter_cache,cache}.dart; `list` prints it, with `--check`
each path is probed on Google's storage.

publish: downloads each artifact from https://storage.googleapis.com (SHA-256 and size recorded),
creates the release `engine-ENGINE` of TARGET (default Boriken-Dev/flutter, the tag on REV) if
missing and uploads each artifact as one flat asset (`/` of the path becomes `__`), then a
`MANIFEST.txt` asset: `path<TAB>sha256<TAB>size<TAB>asset`, paths relative to the storage base URL.
An asset already on the release with the manifest's SHA-256 is neither downloaded again (its size
on Google matches) nor uploaded again, so reruns are cheap and a second platform list adds to the
first. Downloads go to WORK (default ~/.agents/scratch/flutter_artifacts/<engine>) and are
deleted afterwards unless --keep. The artifacts are Google's, unchanged (BSD-licensed Flutter
engine builds); nothing is committed to a branch. Needs gh (logged in).

fetch-tree / serve: GitHub asset URLs are flat and the tool wants
`<base>/flutter_infra_release/flutter/<engine>/...`, so a consumer rebuilds the tree: each
manifest entry is downloaded from the public release (no gh, no login), checked against its
SHA-256 and placed at its path under DIR (default ~/.cache/flutter_artifacts/tree). `serve` does that
then serves DIR on 127.0.0.1 (GET and HEAD, as the Dart SDK scripts probe with HEAD), logs each
request and prints the line to use:
    FLUTTER_STORAGE_BASE_URL=http://127.0.0.1:PORT
Several ENGINEs may share a DIR. Port 0 picks a free one. A request for a path the tree lacks is a
404 and is logged as MISS, which is how a missing artifact shows up. --offline serves DIR as it
is, without reaching GitHub (no ENGINE needed), for a host with no network but loopback.
"""
import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

STORAGE = "https://storage.googleapis.com"
TARGET = "Boriken-Dev/flutter"
ARCHES = ("x64", "arm64")
ALL_PLATFORMS = tuple(f"{os_}-{a}" for os_ in ("windows", "linux") for a in ARCHES)
PREFIX = "flutter_infra_release/flutter"
RAW = "https://raw.githubusercontent.com/{target}/{rev}/bin/internal/{name}"
UA = {"User-Agent": "flutter_artifacts.py"}


def die(msg):
    sys.exit(f"flutter_artifacts: {msg}")


# ------------------------------------------------------------ the list
def raw_version(target, rev, name):
    url = RAW.format(target=target, rev=rev, name=name)
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode().strip()


def artifact_paths(engine, platforms, fonts, gradle):
    """Paths under the storage base URL, in the order the tool asks for them."""
    e = f"{PREFIX}/{engine}"
    out = [f"{e}/engine_stamp.json", f"{e}/flutter-web-sdk.zip", f"{e}/sky_engine.zip", f"{e}/flutter_gpu.zip",
           f"{e}/flutter_patched_sdk.zip", f"{e}/flutter_patched_sdk_product.zip"]
    for p in platforms:
        os_, arch = p.split("-")
        out += [f"{e}/dart-sdk-{p}.zip", f"{e}/{p}/artifacts.zip", f"{e}/{p}/font-subset.zip"]
        if os_ == "windows":
            out += [f"{e}/windows-{arch}-debug/windows-{arch}-flutter.zip",
                    f"{e}/windows-{arch}/flutter-cpp-client-wrapper.zip",
                    f"{e}/windows-{arch}-profile/windows-{arch}-flutter.zip",
                    f"{e}/windows-{arch}-release/windows-{arch}-flutter.zip"]
        else:
            out += [f"{e}/linux-{arch}-{m}/linux-{arch}-flutter-gtk.zip" for m in ("debug", "profile", "release")]
    out += [fonts, gradle]
    return out


def asset_name(path):
    n = path[len("flutter_infra_release/"):] if path.startswith("flutter_infra_release/") else path
    return n.replace("/", "__")


def head(path):
    """(status, size) of a path on Google's storage."""
    try:
        r = urllib.request.urlopen(urllib.request.Request(f"{STORAGE}/{path}", method="HEAD", headers=UA), timeout=60)
        return r.status, int(r.headers.get("Content-Length", -1))
    except urllib.error.HTTPError as e:
        return e.code, -1


# ------------------------------------------------------------- gh
def gh(*args, check=True):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        die(f"gh {' '.join(args[:4])} failed: {r.stderr.strip()[-600:]}")
    return r


def release_assets(target, tag):
    r = gh("api", f"repos/{target}/releases/tags/{tag}", check=False)
    if r.returncode:
        return None
    return {a["name"]: a for a in json.loads(r.stdout)["assets"]}


def read_manifest(target, tag):
    url = f"https://github.com/{target}/releases/download/{tag}/MANIFEST.txt"
    try:
        text = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise
    entries = {}
    for line in text.splitlines():
        if line and not line.startswith("#"):
            path, sha, size, asset = line.split("\t")
            entries[path] = (sha, int(size), asset)
    return entries


def manifest_text(engine, rev, entries):
    lines = [f"# Flutter engine {engine}: artifacts as published by Google at {STORAGE}, unchanged.",
             f"# Mirror commit with the fonts and Gradle wrapper versions: {rev}",
             "# path (under the storage base URL)\tsha256\tsize\tasset"]
    lines += [f"{p}\t{s}\t{n}\t{a}" for p, (s, n, a) in sorted(entries.items())]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------- download
def download(url, dest):
    h, n = hashlib.sha256(), 0
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
            f.write(b)
    tmp.replace(dest)
    return h.hexdigest(), n


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------ commands
def resolve_rev(target, rev):
    if rev and len(rev) == 40:
        return rev
    r = gh("api", f"repos/{target}/commits/{rev or 'main'}", "--jq", ".sha")
    return r.stdout.strip()


def platforms_of(a):
    ps = tuple(a.platforms.split(",")) if a.platforms else ALL_PLATFORMS
    for p in ps:
        if p not in ALL_PLATFORMS:
            die(f"unknown platform {p}")
    return ps


def listing(a):
    rev = resolve_rev(a.target, a.rev)
    fonts = raw_version(a.target, rev, "material_fonts.version")
    gradle = raw_version(a.target, rev, "gradle_wrapper.version")
    return rev, artifact_paths(a.engine, platforms_of(a), fonts, gradle)


def cmd_list(a):
    rev, paths = listing(a)
    for p in paths:
        if a.check:
            status, size = head(p)
            print(f"{status}\t{size}\t{p}")
        else:
            print(p)
    print(f"# {len(paths)} paths, mirror commit {rev}", file=sys.stderr)


NOTES = """Flutter engine `{engine}`: the artifacts `flutter precache` and the first build fetch.

These are Google's published, BSD-licensed Flutter engine and Dart SDK builds, byte for byte as
served from {storage}/{prefix}/{engine}/ (and the Material fonts and Gradle wrapper that the tool
of the same SDK names). Nothing is rebuilt or modified. The engine is the one that the source
mirror's `bin/internal/engine.version` names at commit {rev}.

`MANIFEST.txt` lists each artifact's path under the storage base URL, SHA-256, size and asset name.
Asset names are the path with `/` as `__`, so a consumer rebuilds the tree with
`flutter_artifacts.py serve {engine}` and points FLUTTER_STORAGE_BASE_URL at it.
"""


def cmd_publish(a):
    rev, paths = listing(a)
    tag = f"engine-{a.engine}"
    work = Path(a.work or Path.home() / ".agents" / "scratch" / "flutter_artifacts" / a.engine)
    if a.dry_run:
        print(f"would publish {len(paths)} artifacts to {a.target} release {tag}")
        for p in paths:
            print(" ", p)
        return 0
    assets = release_assets(a.target, tag)
    if assets is None:
        gh("release", "create", tag, "-R", a.target, "--target", rev, "--title", f"Flutter engine {a.engine}",
           "--notes", NOTES.format(engine=a.engine, storage=STORAGE, prefix=PREFIX, rev=rev))
        assets = {}
        print(f"created release {tag}")
    old = read_manifest(a.target, tag) if "MANIFEST.txt" in assets else {}
    entries = dict(old)
    work.mkdir(parents=True, exist_ok=True)
    uploaded = skipped = missing = 0
    try:
        for p in paths:
            name = asset_name(p)
            status, gsize = head(p)
            if status == 404:
                print(f"MISSING on Google: {p}")
                missing += 1
                continue
            if status != 200:
                die(f"HEAD {p}: {status}")
            have = assets.get(name)
            o = old.get(p)
            if o and have and o[1] == gsize and have["size"] == gsize and have.get("digest", f"sha256:{o[0]}") == f"sha256:{o[0]}":
                skipped += 1
                print(f"have     {gsize:>12}  {p}")
                continue
            dest = work / name
            sha, size = download(f"{STORAGE}/{p}", dest)
            entries[p] = (sha, size, name)
            if have and have["size"] == size and have.get("digest") == f"sha256:{sha}":
                skipped += 1
                print(f"same     {size:>12}  {p}")
            else:
                gh("release", "upload", tag, str(dest), "-R", a.target, "--clobber")
                uploaded += 1
                print(f"uploaded {size:>12}  {p}  {sha}")
            if not a.keep:
                dest.unlink()
            entries[p] = (sha, size, name)
        mf = work / "MANIFEST.txt"
        mf.write_text(manifest_text(a.engine, rev, entries), encoding="utf-8", newline="\n")
        gh("release", "upload", tag, str(mf), "-R", a.target, "--clobber")
        total = sum(s for _, s, _ in entries.values())
        print(f"{tag}: {len(entries)} artifacts, {total} bytes; uploaded {uploaded}, kept {skipped}, missing {missing}")
        print(f"https://github.com/{a.target}/releases/tag/{tag}")
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)
    return 1 if missing else 0


def cmd_fetch_tree(a):
    root = Path(a.dir)
    for engine in a.engines:
        tag = f"engine-{engine}"
        entries = read_manifest(a.target, tag)
        if not entries:
            die(f"release {tag} of {a.target} has no MANIFEST.txt")
        for path, (sha, size, asset) in sorted(entries.items()):
            dest = root / path
            if dest.exists() and dest.stat().st_size == size and sha256_file(dest) == sha:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            got, n = download(f"https://github.com/{a.target}/releases/download/{tag}/{asset}", dest)
            if got != sha or n != size:
                dest.unlink()
                die(f"{path}: SHA-256 {got} differs from the manifest's {sha}")
            print(f"fetched {n:>12}  {path}", flush=True)
    return 0


def cmd_serve(a):
    a.dir = a.dir or str(Path.home() / ".cache" / "flutter_artifacts" / "tree")
    if not a.offline:
        if not a.engines:
            die("serve needs an ENGINE, or --offline to serve DIR as it is")
        cmd_fetch_tree(a)
    root = Path(a.dir).resolve()
    logf = open(a.log, "a", buffering=1, encoding="utf-8", newline="\n") if a.log else None
    lock = threading.Lock()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kw):
            super().__init__(*args, directory=str(root), **kw)

        def log_request(self, code="-", size="-"):
            line = f"{'MISS' if str(code) == '404' else 'OK'}\t{code}\t{self.command}\t{self.path}"
            with lock:
                if logf:
                    logf.write(line + "\n")

        def log_error(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer((a.bind, a.port), Handler)
    print(f"FLUTTER_STORAGE_BASE_URL=http://{a.bind if a.bind != '0.0.0.0' else '127.0.0.1'}:{srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, many=False, optional=False):
        p.add_argument("--target", default=TARGET)
        if many:
            p.add_argument("engines", nargs="*" if optional else "+", metavar="ENGINE")
        else:
            p.add_argument("engine", metavar="ENGINE")

    for name in ("list", "publish"):
        p = sub.add_parser(name)
        common(p)
        p.add_argument("--rev")
        p.add_argument("--platforms")
    sub.choices["list"].add_argument("--check", action="store_true", help="HEAD each path on Google's storage")
    p = sub.choices["publish"]
    p.add_argument("--work")
    p.add_argument("--keep", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("fetch-tree")
    p.add_argument("dir", metavar="DIR")
    common(p, many=True)
    p = sub.add_parser("serve")
    common(p, many=True, optional=True)
    p.add_argument("--offline", action="store_true", help="serve DIR as it is, with no request to GitHub")
    p.add_argument("--dir")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--bind", default="127.0.0.1", help="the address to listen on (0.0.0.0 for a container build to reach it)")
    p.add_argument("--log")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        return cmd_list(a) or 0
    return {"publish": cmd_publish, "fetch-tree": cmd_fetch_tree, "serve": cmd_serve}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
