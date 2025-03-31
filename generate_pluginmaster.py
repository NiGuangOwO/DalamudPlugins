import json
import os
from os.path import getmtime
from zipfile import ZipFile

BRANCH = os.environ["GITHUB_REF"].split("refs/heads/")[-1]
DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/latest.zip"
TESTING_DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/testing/latest.zip"
GLOBAL_DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/global/latest.zip"

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
]


def main():
    master = extract_manifests()
    master = [trim_manifest(manifest) for manifest in master]
    add_extra_fields(master)
    write_master(master)
    last_update()


def extract_manifests():
    manifests = []
    for dirpath, dirnames, filenames in os.walk("./plugins"):
        if "testing" in dirnames:
            dirnames.remove("testing")
        if "global" in dirnames:
            dirnames.remove("global")
        if "latest.zip" not in filenames:
            continue

        plugin_name = dirpath.split("/")[-1]
        base_zip = f"{dirpath}/latest.zip"

        with ZipFile(base_zip) as z:
            base_manifest = json.loads(z.read(f"{plugin_name}.json").decode("utf-8"))

            testing_zip = f"{dirpath}/testing/latest.zip"
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

            global_zip = f"{dirpath}/global/latest.zip"
            if os.path.exists(global_zip):
                with ZipFile(global_zip) as gz:
                    global_manifest = json.loads(
                        gz.read(f"{plugin_name}.json").decode("utf-8")
                    )
                    global_manifest["Name"] = f"{global_manifest['Name']} (API12))"
                    manifests.append(global_manifest)
    return manifests


def add_extra_fields(manifests):
    for manifest in manifests:
        is_global = manifest["Name"].endswith("(API12)")

        if is_global:
            manifest["DownloadLinkInstall"] = GLOBAL_DOWNLOAD_URL.format(
                branch=BRANCH,
                plugin_name=manifest["InternalName"],
            )
        else:
            manifest["DownloadLinkInstall"] = DOWNLOAD_URL.format(
                branch=BRANCH, plugin_name=manifest["InternalName"]
            )

        for src, targets in DUPLICATES.items():
            for target in targets:
                if target not in manifest:
                    manifest[target] = manifest[src]

        if "TestingAssemblyVersion" in manifest and not is_global:
            manifest["DownloadLinkTesting"] = TESTING_DOWNLOAD_URL.format(
                branch=BRANCH, plugin_name=manifest["InternalName"]
            )

        manifest["DownloadCount"] = 0


def write_master(master):
    with open("pluginmaster.json", "w") as f:
        json.dump(master, f, indent=4)


def trim_manifest(plugin):
    return {k: plugin[k] for k in TRIMMED_KEYS if k in plugin}


def last_update():
    with open("pluginmaster.json", encoding="utf-8") as f:
        master = json.load(f)

    for plugin in master:
        if plugin["Name"].endswith("_global"):
            file_path = f"plugins/{plugin['InternalName']}/global/latest.zip"
        else:
            file_path = f"plugins/{plugin['InternalName']}/latest.zip"

        modified = int(getmtime(file_path))
        if "LastUpdate" not in plugin or modified != int(plugin.get("LastUpdate", 0)):
            plugin["LastUpdate"] = str(modified)

    with open("pluginmaster.json", "w", encoding="utf-8") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
