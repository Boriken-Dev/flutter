# Flutter container images (the `images` branch of Boriken-Dev/flutter)

This orphan branch holds the tooling that builds container images of the Flutter SDK for web, Linux and Windows builds, made from Boriken Dev's
mirrors. Building from one of them makes no request to Google's storage or to `flutter/flutter`.

| Image | Platforms | Builds |
| --- | --- | --- |
| `ghcr.io/boriken-dev/flutter-web` | linux/amd64, linux/arm64 | `flutter build web` |
| `ghcr.io/boriken-dev/flutter-linux` | linux/amd64, linux/arm64 | `flutter build linux` (clang, cmake, ninja, GTK 3) |
| `ghcr.io/boriken-dev/flutter-windows` | windows/amd64 (Windows Server 2025, 10.0.26100) | `flutter build windows` (Visual Studio Build Tools) |

Tags: `:<first 10 characters of the mirror commit>` and `:<Flutter version>` (for example `:3.51.0-1.0.pre-291`),
each an index over the architectures. `:<commit>-<arch>` is one architecture's image.

## How they are made

Each image repeats the toolchain recipe of [gmeligio/flutter-docker-image](https://github.com/gmeligio/flutter-docker-image)
(MIT, Copyright gmeligio; commit `05eeacdf86d0e7376f86106e61718d67cc2a922c`) stage by stage, up to the point where
it installs Flutter, and then adds Flutter from Boriken Dev's mirrors. It does not start from their finished images: a
layer that holds their Flutter SDK would stay in the image after a later layer deleted it.

1. The toolchain, in the Containerfile itself:
   - web and Linux, both architectures: `debian:13.7-slim` by digest, `curl git lcov ca-certificates unzip` (Linux adds
     `clang cmake ninja-build pkg-config libgtk-3-dev`), the `flutter` user (uid 1001) and the entrypoint, as in their
     `android.Dockerfile`. Their exact apt versions are not repeated: the archive no longer serves two of them.
   - Windows: Server Core `ltsc2025` by digest, MinGit 2.56.1 (checked against its SHA-256), the same user paths and
     `PATH`, and the Visual Studio Build Tools with `VC.CMake.Project`, `Windows11SDK.22621` and `Workload.VCTools`, as in
     their `windows.Dockerfile`. The installer, its logs, `TEMP` and the package cache are removed in the layer that
     makes them, and the build prints the installed versions.
2. Clone [Boriken-Dev/flutter](https://github.com/Boriken-Dev/flutter) at the pinned commit as branch `main`, with
   its tags (Flutter names its version from the newest tag and the commits since it).
3. Run `flutter precache` for the platform. The engine, the Dart SDK and the web artifacts come from the release
   `engine-<hash>` of Boriken-Dev/flutter: Google's files byte for byte, with a SHA-256 manifest. The workflow downloads
   them (`tools/flutter_artifacts.py fetch-tree`, checking every hash), serves them on the runner and hands that address
   to the build as `FLUTTER_STORAGE_BASE_URL`. Nothing is copied into a layer, and the served log must show no missed request.
4. Before the push, a throwaway container of the image runs `flutter --version` and builds a `flutter create` sample app,
   with the storage address set to a dead port, and its engine hash must equal the pin. The sample app and its caches
   never enter the image. The job log prints `docker history`, the size of each layer.

The images carry no Rust, Android SDK or browser.

## Pins

| | |
| --- | --- |
| Mirror commit | `33d7f282aaef7665096e5acd368d3c2ee226f6bb` (Boriken-Dev/flutter `main`) |
| Engine | `89573e968cbf3febdf4f07189cc2bef6cbef830b` |
| gmeligio recipe | `gmeligio/flutter-docker-image` at `05eeacdf86d0e7376f86106e61718d67cc2a922c` |
| Debian | `debian:13.7-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2` |
| Server Core | `mcr.microsoft.com/windows/servercore:ltsc2025@sha256:a43c2d41a3d6e940dec865731e2f5db5c3e03f705f5300ef0b5817d3e01ecfb1` |
| MinGit | 2.56.1, SHA-256 `baa40c1b8d5897826f47c2b819156553b89833bc52cb42cdfca7d1f0faeed34a` |
| Visual Studio Build Tools | the `17/release` channel's installer; Windows 11 SDK build 22621 |

The defaults in `build.yml` are the mirror and engine pins; the rest are in the Containerfiles.


## Running the workflow

`build.yml` here is a reusable workflow. GitHub starts a manual run only from the default branch, so
`.github/workflows/flutter-images.yml` on `stable` (one commit on top of the mirrored head, put back by `flutter_mirror.py`
at each sync) calls it from this branch. The workflow runs only when started by hand, never on a push or a schedule:

```sh
gh workflow run flutter-images.yml -R Boriken-Dev/flutter \
  -f mirror=<commit of Boriken-Dev/flutter> -f engine=<its bin/internal/engine.version> -f platforms=web,linux,windows
```

`plan` checks that the commit names that engine and that the engine's release exists; `unix` builds web and Linux on
`ubuntu-24.04` (amd64) and `ubuntu-24.04-arm` (arm64); `windows` builds on `windows-2025` in Windows-container mode with
process isolation, which needs the base's Windows build (10.0.26100); `manifest` joins the architectures. To publish a
new engine, run `flutter_artifacts.py publish <engine>` from the agent tools first.

## Layout

- `containers/Containerfile.{web,linux,windows}` and the entrypoints beside them: generated by `flutter_sdk.py image <platform> --emit containers`
  of the agent tools; this branch is the source of truth for them once committed, so edit them here.
- `tools/build.py`: builds, checks and pushes one image on a runner.
- `tools/flutter_artifacts.py`: fetches and serves the engine release (copied from the agent tools, MIT here).

## Licenses

This branch: MIT (`LICENSE`). Flutter and the engine: BSD-3-Clause, Google. gmeligio's Dockerfiles and the
toolchain recipe repeated from them: MIT, Copyright gmeligio. The images also hold Debian, Git, Visual Studio Build
Tools and other software under their own licenses.
