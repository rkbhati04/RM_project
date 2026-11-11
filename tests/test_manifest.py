import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from probe_and_capture import MANIFEST_FIELDS, upgrade_manifest, validate_manifest


class ManifestMigrationTests(unittest.TestCase):
    def test_legacy_manifest_is_migrated_without_losing_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            old_fields = ["timestamp", "network", "resolver", "protocol", "workload", "domain", "repeat", "returncode", "latency_s", "packets", "bytes", "status", "server_ips", "pcap_path", "note"]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=old_fields)
                writer.writeheader(); writer.writerow({"timestamp": "1", "network": "airtel", "resolver": "google", "protocol": "doh"})
            upgrade_manifest(path)
            self.assertEqual(validate_manifest(path), {len(MANIFEST_FIELDS)})
            with path.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["resolver"], "google")
            self.assertEqual(row["run_id"], "")

    def test_migration_backs_up_and_hashes_raw_public_ip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            old_fields = ["timestamp", "network", "public_ip", "resolver"]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=old_fields)
                writer.writeheader()
                writer.writerow({"timestamp": "1", "network": "airtel",
                                 "public_ip": "203.0.113.7", "resolver": "google"})
            upgrade_manifest(path)
            backup = path.with_name("manifest_pre_migration.csv")
            self.assertTrue(backup.exists())
            with path.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertTrue(row["public_ip"].startswith("hash:"))
            self.assertNotIn("203.0.113.7", path.read_text(encoding="utf-8"))
            self.assertEqual(validate_manifest(path), {len(MANIFEST_FIELDS)})

    def test_invalid_row_length_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.csv"
            path.write_text(",".join(MANIFEST_FIELDS) + "\nonly,one\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_manifest(path)


if __name__ == "__main__":
    unittest.main()
