from __future__ import annotations

import plistlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import deploy  # noqa: E402


class DeployScriptTests(unittest.TestCase):
    def make_zip(self, archive_path: Path, *members: str) -> None:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path, "w") as handle:
            for member in members:
                handle.writestr(member, "stub")

    def make_mock_xcode(self, root: Path, app_name: str, version: str, bundle_name: str = "Xcode") -> Path:
        app_path = root / app_name
        info_path = app_path / "Contents" / "Info.plist"
        device_support_dir = app_path / "Contents" / "Developer" / "Platforms" / "iPhoneOS.platform" / "DeviceSupport"
        device_support_dir.mkdir(parents=True, exist_ok=True)
        with info_path.open("wb") as handle:
            plistlib.dump(
                {
                    "CFBundleName": bundle_name,
                    "CFBundleShortVersionString": version,
                },
                handle,
            )
        return app_path

    def test_scan_support_inventory_tracks_archives_and_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            device_support_root = temp_root / "DeviceSupport"
            placeholder_root = device_support_root / "placeholders"

            self.make_zip(device_support_root / "16.4.zip", "16.4/DeveloperDiskImage.dmg")
            deploy.ensure_placeholder_versions(
                placeholder_root=placeholder_root,
                start_major=17,
                end_major=18,
            )

            inventory = deploy.scan_support_inventory(
                device_support_root=device_support_root,
                placeholder_root=placeholder_root,
            )
            by_version = {item.version: item for item in inventory}

            self.assertEqual(by_version["16.4"].artifact_count, 1)
            self.assertEqual(by_version["16.4"].status, "Available")
            self.assertEqual(by_version["17.0"].artifact_count, 0)
            self.assertEqual(by_version["17.0"].status, "Placeholder")
            self.assertEqual(by_version["18.0"].status, "Placeholder")

    def test_sync_readme_replaces_generated_block(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            device_support_root = temp_root / "DeviceSupport"
            placeholder_root = device_support_root / "placeholders"
            readme_path = temp_root / "README.md"

            self.make_zip(device_support_root / "16.4.zip", "16.4/DeveloperDiskImage.dmg")
            deploy.ensure_placeholder_versions(
                placeholder_root=placeholder_root,
                start_major=17,
                end_major=17,
            )

            readme_path.write_text(
                "\n".join(
                    [
                        "# Test",
                        "",
                        deploy.SUPPORT_TABLE_START,
                        "stale content",
                        deploy.SUPPORT_TABLE_END,
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            changed = deploy.sync_readme(
                readme_path=readme_path,
                device_support_root=device_support_root,
                placeholder_root=placeholder_root,
            )

            self.assertTrue(changed)
            readme_text = readme_path.read_text(encoding="utf-8")
            self.assertIn("| 16.4 | Available | 1 |", readme_text)
            self.assertIn("| 17.0 | Placeholder | 0 |", readme_text)

    def test_normalize_installation_target_accepts_app_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            app_path = self.make_mock_xcode(
                root=temp_root,
                app_name="Xcode_17_Beta.app",
                version="17.0",
                bundle_name="Xcode Beta",
            )

            installation = deploy.normalize_installation_target(app_path, source="test")

            self.assertEqual(installation.version, "17.0")
            self.assertTrue(installation.is_beta)
            self.assertTrue(installation.is_ready)
            self.assertEqual(installation.display_name, "Xcode_17_Beta.app")

    def test_build_install_plan_skips_existing_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            device_support_root = temp_root / "DeviceSupport"
            self.make_zip(device_support_root / "16.4.zip", "16.4/DeveloperDiskImage.dmg")
            self.make_zip(device_support_root / "17.0.zip", "17.0/DeveloperDiskImage.dmg")

            app_path = self.make_mock_xcode(
                root=temp_root,
                app_name="Xcode.app",
                version="16.4",
            )
            target_dir = (
                app_path
                / "Contents"
                / "Developer"
                / "Platforms"
                / "iPhoneOS.platform"
                / "DeviceSupport"
            )
            (target_dir / "16.4").mkdir(parents=True, exist_ok=True)

            installation = deploy.normalize_installation_target(app_path, source="test")
            matched_archives, pending_archives = deploy.build_install_plan(
                installation=installation,
                device_support_root=device_support_root,
            )

            self.assertEqual(len(matched_archives), 2)
            self.assertEqual([archive.display_name for archive in pending_archives], ["17.0"])


if __name__ == "__main__":
    unittest.main()
