import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location("generator", Path(__file__).resolve().parents[1] / "generate_pluginmaster.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class IndexGeneration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def local(self, name="OtherPlugin", value="1.0.0.1", subfolder=None):
        folder = self.root / "plugins" / name
        if subfolder:folder /= subfolder
        folder.mkdir(parents=True, exist_ok=True)
        data = {"Name": name, "InternalName": name, "AssemblyVersion": value, "DalamudApiLevel": 15}
        with ZipFile(folder / "latest.zip", "w") as archive:archive.writestr(name + ".json", json.dumps(data))
        return data

    def external(self, value="1.0.0.46"):
        folder = self.root / "plugins/DalamudMCP";folder.mkdir(parents=True, exist_ok=True)
        data = {"Name": "DalamudMCP", "InternalName": "DalamudMCP", "AssemblyVersion": value, "DalamudApiLevel": 15}
        record = {"schemaVersion": 1, "sourceRepository": "NiGuangOwO/DalamudMCP", "version": value,
                  "tag": "v" + value, "assetName": "latest.zip", "sha256": "a" * 64, "publishedAtUnix": 12345,
                  "downloadUrl": f"https://github.com/NiGuangOwO/DalamudMCP/releases/download/v{value}/latest.zip"}
        (folder / "DalamudMCP.json").write_text(json.dumps(data))
        (folder / "release.json").write_text(json.dumps(record))
        return folder, record

    def test_external_without_binary(self):
        _, record = self.external()
        entry = generator.generate(self.root)[0]
        self.assertEqual(entry["DownloadLinkInstall"], record["downloadUrl"])
        self.assertEqual(entry["DownloadLinkUpdate"], record["downloadUrl"])
        self.assertEqual(entry["LastUpdate"], "12345")

    def test_external_wins_over_old_zip(self):
        self.local("DalamudMCP", "1.0.0.45");self.external()
        self.assertEqual(generator.generate(self.root)[0]["AssemblyVersion"], "1.0.0.46")

    def test_missing_descriptor_cannot_fall_back_to_old_zip(self):
        self.local("DalamudMCP", "1.0.0.45");folder, _ = self.external()
        generator.generate(self.root)
        before = (self.root / "pluginmaster.json").read_bytes()
        (folder / "release.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing release.json"):
            generator.generate(self.root)
        self.assertEqual((self.root / "pluginmaster.json").read_bytes(), before)

    def test_missing_descriptor_cannot_silently_drop_plugin(self):
        folder, _ = self.external();generator.generate(self.root)
        before = (self.root / "pluginmaster.json").read_bytes()
        (folder / "release.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing release.json"):
            generator.generate(self.root)
        self.assertEqual((self.root / "pluginmaster.json").read_bytes(), before)

    def test_removed_external_folder_requires_explicit_index_removal(self):
        folder, _ = self.external();generator.generate(self.root)
        before = (self.root / "pluginmaster.json").read_bytes()
        (folder / "release.json").unlink();(folder / "DalamudMCP.json").unlink();folder.rmdir()
        with self.assertRaisesRegex(ValueError, "Missing release.json"):
            generator.generate(self.root)
        self.assertEqual((self.root / "pluginmaster.json").read_bytes(), before)

    def test_inconsistent_metadata_does_not_replace_index(self):
        folder, record = self.external();generator.generate(self.root)
        before = (self.root / "pluginmaster.json").read_bytes()
        record["version"] = "1.0.0.47"
        (folder / "release.json").write_text(json.dumps(record))
        with self.assertRaises(ValueError):generator.generate(self.root)
        self.assertEqual((self.root / "pluginmaster.json").read_bytes(), before)

    def test_floating_or_non_github_link_is_rejected(self):
        folder, record = self.external()
        for url in ("https://github.com/NiGuangOwO/DalamudMCP/releases/latest/download/latest.zip", "https://example.com/latest.zip"):
            record["downloadUrl"] = url;(folder / "release.json").write_text(json.dumps(record))
            with self.subTest(url=url), self.assertRaises(ValueError):generator.generate(self.root)

    def test_other_plugin_and_idempotence(self):
        self.local();generator.generate(self.root)
        before = json.loads((self.root / "pluginmaster.json").read_text())
        self.external();generator.generate(self.root)
        after = json.loads((self.root / "pluginmaster.json").read_text())
        self.assertEqual(next(e for e in after if e["InternalName"] == "OtherPlugin"), before[0])
        saved = (self.root / "pluginmaster.json").read_bytes();generator.generate(self.root)
        self.assertEqual(saved, (self.root / "pluginmaster.json").read_bytes())

    def test_legacy_testing_and_subfolder_links(self):
        self.local();self.local(subfolder="global");self.local(value="1.0.0.2", subfolder="testing")
        entries = generator.generate(self.root)
        self.assertEqual(len(entries), 2)
        base, variant = entries
        self.assertEqual(base["TestingAssemblyVersion"], "1.0.0.2")
        self.assertIn("/testing/latest.zip", base["DownloadLinkTesting"])
        self.assertIn("/global/latest.zip", variant["DownloadLinkInstall"])
        self.assertEqual(variant["Name"], "OtherPlugin (global)")


if __name__ == "__main__":unittest.main()
