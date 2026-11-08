"""Generate a stable plugin index from local packages or verified release metadata."""
import json
import os
from pathlib import Path
import re
from zipfile import ZipFile

DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/latest.zip"
SUB_DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/{subfolder}/latest.zip"
TRIMMED_KEYS = (
    "Author", "Name", "Punchline", "Description", "Tags", "InternalName", "RepoUrl",
    "Changelog", "AssemblyVersion", "ApplicableVersion", "DalamudApiLevel",
    "TestingAssemblyVersion", "TestingDalamudApiLevel", "IconUrl", "ImageUrls",
    "DownloadLinkInstall", "DownloadLinkUpdate", "DownloadLinkTesting", "LastUpdate",
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def external_manifest(folder):
    record = read_json(folder / "release.json")
    manifest = read_json(folder / (folder.name + ".json"))
    value = record["version"]
    repo = record["sourceRepository"]
    expected = f"https://github.com/{repo}/releases/download/v{value}/latest.zip"
    if (record.get("schemaVersion") != 1
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+", value)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)
            or record["tag"] != "v" + value or record["assetName"] != "latest.zip"
            or record["downloadUrl"] != expected
            or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
            or manifest["AssemblyVersion"] != value
            or manifest["InternalName"] != folder.name
            or int(record["publishedAtUnix"]) <= 0):
        raise ValueError("Invalid or inconsistent external release: " + folder.name)
    manifest["DownloadLinkInstall"] = expected
    manifest["DownloadLinkUpdate"] = expected
    manifest["LastUpdate"] = str(record["publishedAtUnix"])
    return manifest


def local_manifest(package, plugin_name):
    with ZipFile(package) as archive:
        return json.loads(archive.read(plugin_name + ".json").decode("utf-8-sig"))


def generate(root=Path("."), branch="main"):
    root = Path(root)
    index_path = root / "pluginmaster.json"
    previous = read_json(index_path) if index_path.exists() else []
    old = {(entry["InternalName"], entry.get("DownloadLinkInstall")): entry for entry in previous}
    external_plugins = {
        entry["InternalName"] for entry in previous
        if "/releases/download/" in entry.get("DownloadLinkInstall", "")
    }
    entries = []
    plugins = root / "plugins"
    for name in external_plugins:
        if not (plugins / name / "release.json").is_file():
            raise ValueError("Missing release.json for external plugin: " + name)
    for folder in sorted(plugins.iterdir()) if plugins.exists() else []:
        if not folder.is_dir():
            continue
        if (folder / "release.json").exists():
            base, package = external_manifest(folder), None
        elif (folder / "latest.zip").exists():
            package = folder / "latest.zip"
            base = local_manifest(package, folder.name)
        else:
            continue
        testing = folder / "testing/latest.zip"
        if testing.exists():
            test = local_manifest(testing, folder.name)
            base["TestingAssemblyVersion"] = test.get("AssemblyVersion")
            base["TestingDalamudApiLevel"] = test.get("DalamudApiLevel")
            base["DownloadLinkTesting"] = SUB_DOWNLOAD_URL.format(
                branch=branch, plugin_name=folder.name, subfolder="testing")
        variants = [(base, package, None)]
        for child in sorted(folder.iterdir()):
            if child.is_dir() and child.name != "testing" and (child / "latest.zip").exists():
                variant = local_manifest(child / "latest.zip", folder.name)
                variant["Name"] += " (" + child.name + ")"
                variants.append((variant, child / "latest.zip", child.name))
        for manifest, package, subfolder in variants:
            entry = {key: manifest[key] for key in TRIMMED_KEYS if key in manifest}
            if "DownloadLinkInstall" not in entry:
                template = SUB_DOWNLOAD_URL if subfolder else DOWNLOAD_URL
                entry["DownloadLinkInstall"] = template.format(
                    branch=branch, plugin_name=folder.name, subfolder=subfolder)
            entry.setdefault("DownloadLinkUpdate", entry["DownloadLinkInstall"])
            entry["DownloadCount"] = 0
            if "LastUpdate" not in entry:
                existing = old.get((entry["InternalName"], entry["DownloadLinkInstall"]))
                compare = lambda item: {key: val for key, val in item.items() if key != "LastUpdate"}
                if existing and compare(existing) == compare(entry):
                    entry["LastUpdate"] = existing["LastUpdate"]
                else:
                    entry["LastUpdate"] = str(int(package.stat().st_mtime))
            entries.append(entry)
    if entries != previous:
        index_path.write_text(json.dumps(entries, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return entries


if __name__ == "__main__":
    generate(Path.cwd(), os.environ.get("GITHUB_REF", "refs/heads/main").removeprefix("refs/heads/"))
