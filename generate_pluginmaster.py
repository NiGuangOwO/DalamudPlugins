import json
import os
from os.path import getmtime
from zipfile import ZipFile

BRANCH = os.environ["GITHUB_REF"].split("refs/heads/")[-1]
DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/latest.zip"
TESTING_DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/testing/latest.zip"
# Generic subfolder download URL. Use with subfolder name, e.g. 'global' or other folder.
SUB_DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/{subfolder}/latest.zip"

DUPLICATES = {
    "DownloadLinkInstall": ["DownloadLinkUpdate"],
}

TRIMMED_KEYS = [
    "Author",
    "Name",
    "Punchline",
    "Description",
    "Tags",
    "InternalName",
    "RepoUrl",
    "Changelog",
    "AssemblyVersion",
    "ApplicableVersion",
    "DalamudApiLevel",
    "TestingAssemblyVersion",
    "TestingDalamudApiLevel",
    "IconUrl",
    "ImageUrls",
    "Subfolder",
]


def main():
    master = extract_manifests()
    master = [trim_manifest(manifest) for manifest in master]
    add_extra_fields(master)
    write_master(master)
    last_update()


def extract_manifests():
    manifests = []
    plugins_root = os.path.join(".", "plugins")
    if not os.path.isdir(plugins_root):
        return manifests

    for plugin_folder in sorted(os.listdir(plugins_root)):
        plugin_dir = os.path.join(plugins_root, plugin_folder)
        if not os.path.isdir(plugin_dir):
            continue

        plugin_name = plugin_folder
        base_zip = os.path.join(plugin_dir, "latest.zip")
        # If no base latest.zip, skip this plugin folder
        if not os.path.exists(base_zip):
            continue

        # Read base manifest
        with ZipFile(base_zip) as z:
            base_manifest = json.loads(z.read(f"{plugin_name}.json").decode("utf-8"))
            base_manifest["Subfolder"] = None

            # If there's a testing sub-zip, merge its assembly/api info into base manifest
            testing_zip = os.path.join(plugin_dir, "testing", "latest.zip")
            if os.path.exists(testing_zip):
                with ZipFile(testing_zip) as tz:
                    testing_manifest = json.loads(
                        tz.read(f"{plugin_name}.json").decode("utf-8")
                    )
                    base_manifest["TestingAssemblyVersion"] = testing_manifest.get(
                        "AssemblyVersion"
                    )
                    base_manifest["TestingDalamudApiLevel"] = testing_manifest.get(
                        "DalamudApiLevel"
                    )

            manifests.append(base_manifest)

        # Scan other subfolders in this plugin folder (e.g. global, other variants)
        for sub in sorted(os.listdir(plugin_dir)):
            sub_path = os.path.join(plugin_dir, sub)
            if not os.path.isdir(sub_path):
                continue
            if sub == "testing":
                continue

            sub_zip = os.path.join(sub_path, "latest.zip")
            if os.path.exists(sub_zip):
                with ZipFile(sub_zip) as sz:
                    sub_manifest = json.loads(
                        sz.read(f"{plugin_name}.json").decode("utf-8")
                    )
                    sub_manifest["Subfolder"] = sub
                    sub_manifest["Name"] = f"{sub_manifest['Name']} ({sub})"
                    manifests.append(sub_manifest)

    return manifests


def add_extra_fields(manifests):
    for manifest in manifests:
        sub = manifest.get("Subfolder")
        if sub:
            manifest["DownloadLinkInstall"] = SUB_DOWNLOAD_URL.format(
                branch=BRANCH, plugin_name=manifest["InternalName"], subfolder=sub
            )
        else:
            manifest["DownloadLinkInstall"] = DOWNLOAD_URL.format(
                branch=BRANCH, plugin_name=manifest["InternalName"]
            )

        for src, targets in DUPLICATES.items():
            for target in targets:
                if target not in manifest:
                    manifest[target] = manifest[src]

        if "TestingAssemblyVersion" in manifest and not manifest.get("Subfolder"):
            manifest["DownloadLinkTesting"] = TESTING_DOWNLOAD_URL.format(
                branch=BRANCH, plugin_name=manifest["InternalName"]
            )

        manifest["DownloadCount"] = 0


def write_master(master):
    # Remove Subfolder field before writing to JSON (internal use only)
    for plugin in master:
        plugin.pop("Subfolder", None)
    with open("pluginmaster.json", "w") as f:
        json.dump(master, f, indent=4)


def trim_manifest(plugin):
    return {k: plugin[k] for k in TRIMMED_KEYS if k in plugin}


def last_update():
    with open("pluginmaster.json", encoding="utf-8") as f:
        master = json.load(f)

    for plugin in master:
        sub = plugin.get("Subfolder")
        if sub:
            file_path = os.path.join(
                "plugins", plugin["InternalName"], sub, "latest.zip"
            )
        else:
            file_path = os.path.join("plugins", plugin["InternalName"], "latest.zip")

        modified = int(getmtime(file_path))
        if "LastUpdate" not in plugin or modified != int(plugin.get("LastUpdate", 0)):
            plugin["LastUpdate"] = str(modified)

    with open("pluginmaster.json", "w", encoding="utf-8") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
