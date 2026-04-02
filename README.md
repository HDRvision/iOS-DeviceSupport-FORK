# HDRvision iOS DeviceSupport

![Maintained by HDRvision](https://img.shields.io/badge/Maintained%20by-HDRvision-111111?style=for-the-badge&labelColor=000000&color=2f3136)
![Automated via Codex](https://img.shields.io/badge/Automated%20via-Codex-111111?style=for-the-badge&labelColor=000000&color=2f3136)
![GitHub Actions macOS](https://img.shields.io/badge/Tested%20on-GitHub%20Actions%20macOS-111111?style=for-the-badge&labelColor=000000&color=2f3136)

> Maintained by HDRvision. Automated via Codex. Tested on GitHub Actions macOS runners.

This repository continues the archived `iGhibli/iOS-DeviceSupport` project and keeps iOS DeviceSupport bundles organized for modern Xcode installations. The fork preserves the original zip-based archive layout, adds safer deployment automation for Python 3.10+, and keeps forward-looking placeholders reserved through iOS 26.0.

## Why this fork exists

When Xcode does not ship with the DeviceSupport bundle for a connected iPhone or iPad, developers get blocked from debugging on real hardware. The original project stopped at iOS 16.0. HDRvision is reviving the workflow, modernizing the tooling, and opening the door for community-contributed support files for newer iOS releases.

## What changed in HDRvision

- `deploy.py` now supports Python 3.10+ with stronger path validation, dry-run planning, JSON output, and clear permission/path errors.
- Xcode discovery works with `DEVELOPER_DIR`, `xcode-select`, `Xcode.app`, `Xcode-beta.app`, `Xcode_16.x.app`, `Xcode_17.x.app`, and future naming variants that match `Xcode*.app`.
- The README support matrix is generated from the repository contents instead of being maintained by hand.
- Placeholder directories are reserved for iOS `17.0` through `26.0`.
- GitHub Actions validates the tooling on `macos-latest` so macOS-specific checks do not depend on a personal Mac.

## Repository layout

```text
DeviceSupport/
  *.zip
  placeholders/
    17.0/
    18.0/
    ...
    26.0/
deploy.py
.github/workflows/test-macos.yml
tests/
```

## Usage

Install any missing archives into the selected Xcode:

```bash
python3 deploy.py
```

Preview what would happen without writing files:

```bash
python3 deploy.py --dry-run
```

Target a specific Xcode bundle, beta build, or developer directory:

```bash
python3 deploy.py --dry-run --target /Applications/Xcode-beta.app
python3 deploy.py --target /Applications/Xcode_16.4.app
python3 deploy.py --target /Applications/Xcode.app/Contents/Developer
```

Filter to a specific iOS version string:

```bash
python3 deploy.py --dry-run --version 16.4
```

Inspect the repository inventory:

```bash
python3 deploy.py inventory
python3 deploy.py inventory --json
```

Regenerate the README support matrix after adding or removing archives:

```bash
python3 deploy.py sync-readme
```

Rebuild future-version placeholders:

```bash
python3 deploy.py ensure-placeholders --start-major 17 --end-major 26
```

## Working from Windows or Linux

You can still run inventory, README sync, and placeholder generation from Windows or Linux. Actual Xcode discovery and install validation are intentionally exercised in GitHub Actions on macOS runners.

## GitHub Actions validation

The macOS workflow does four things on every push and pull request:

1. Runs the Python test suite.
2. Verifies the placeholder tree and generated README are current.
3. Executes `deploy.py --dry-run` against the real Xcode installation on the GitHub runner.
4. Executes `deploy.py --dry-run` against a mock Xcode bundle to validate path handling without modifying the runner.

## Adding new DeviceSupport archives

1. Add the verified `.zip` archive directly under `DeviceSupport/`.
2. Run `python3 deploy.py sync-readme`.
3. Open a pull request with the iOS version, build number, and source Xcode build noted in the description.
4. Let GitHub Actions confirm the deployment logic still resolves Xcode correctly on macOS.

## Call For Contributors

If you have access to newer DeviceSupport bundles, especially for iOS `17.0` through `26.0`, contributions are welcome.

- Upload verified archives from shipping Xcode releases or clearly labeled beta builds.
- Preserve the existing naming convention so the version can be detected from the filename.
- Include any useful provenance in the archive name, such as the source Xcode build or seed.
- Open issues or pull requests if a new Xcode packaging pattern appears in macOS 2026 or later.

## Support matrix

<!-- support-table:start -->
> Latest verified support archive in this repository: **iOS 16.4**.
> Placeholder directories are reserved through **iOS 26.0**.

| iOS Version | Status | Artifacts | Notes |
| --- | --- | ---: | --- |
| 8.0 | Available | 1 | 1 archive |
| 8.1 | Available | 1 | 1 archive |
| 8.2 | Available | 1 | 1 archive |
| 8.3 | Available | 1 | 1 archive |
| 8.4 | Available | 1 | 1 archive |
| 9.0 | Available | 1 | 1 archive |
| 9.1 | Available | 1 | 1 archive |
| 9.2 | Available | 1 | 1 archive |
| 9.3 | Available | 1 | 1 archive |
| 10.0 | Available | 2 | 2 archives |
| 10.1 | Available | 2 | 2 archives |
| 10.2 | Available | 2 | 2 archives |
| 10.3 | Available | 2 | 2 archives |
| 11.0 | Available | 1 | 1 archive |
| 11.1 | Available | 2 | 2 archives |
| 11.2 | Available | 2 | 2 archives |
| 11.3 | Available | 3 | 3 archives |
| 11.4 | Available | 4 | 4 archives |
| 12.0 | Available | 8 | 8 archives |
| 12.1 | Available | 5 | 5 archives |
| 12.2 | Available | 3 | 3 archives |
| 12.3 | Available | 1 | 1 archive |
| 12.4 | Available | 2 | 2 archives |
| 13.0 | Available | 2 | 2 archives |
| 13.1 | Available | 1 | 1 archive |
| 13.2 | Available | 4 | 4 archives |
| 13.3 | Available | 2 | 2 archives |
| 13.4 | Available | 3 | 3 archives |
| 13.5 | Available | 4 | 4 archives |
| 13.6 | Available | 2 | 2 archives |
| 13.7 | Available | 2 | 2 archives |
| 14.0 | Available | 8 | 8 archives |
| 14.1 | Available | 2 | 2 archives |
| 14.2 | Available | 5 | 5 archives |
| 14.3 | Available | 3 | 3 archives |
| 14.4 | Available | 4 | 4 archives |
| 14.5 | Available | 5 | 5 archives |
| 14.6 | Available | 1 | 1 archive |
| 15.0 | Available | 8 | 8 archives |
| 15.2 | Available | 2 | 2 archives |
| 15.4 | Available | 3 | 3 archives |
| 15.5 | Available | 2 | 2 archives |
| 15.6 | Available | 2 | 2 archives |
| 15.7 | Available | 1 | 1 archive |
| 16.0 | Available | 6 | 6 archives |
| 16.1 | Available | 4 | 4 archives |
| 16.4 | Available | 3 | 3 archives |
| 17.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 18.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 19.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 20.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 21.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 22.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 23.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 24.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 25.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
| 26.0 | Placeholder | 0 | Reserved placeholder awaiting a contributed DeviceSupport bundle |
<!-- support-table:end -->

## Maintenance note

HDRvision owns the current maintenance roadmap for this fork. The project stays intentionally lightweight: the repository stores archives, `deploy.py` handles installation and metadata generation, and GitHub Actions provides the macOS validation surface that is not available from Windows or Linux.
