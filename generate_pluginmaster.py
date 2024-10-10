import json
import os
from os.path import getmtime
from sys import argv
from time import time
from zipfile import ZIP_DEFLATED, ZipFile

# 从环境变量中获取当前分支名称
BRANCH = os.environ["GITHUB_REF"].split("refs/heads/")[-1]
# 定义插件安装和测试的下载链接
DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/latest.zip"
TESTING_DOWNLOAD_URL = "https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/testing/latest.zip"

# 插件元数据的默认值
DEFAULTS = {
    "IsHide": False,
    "IsTestingExclusive": False,
    "ApplicableVersion": "any",
}

# 插件元数据中重复键的映射
DUPLICATES = {
    "DownloadLinkInstall": ["DownloadLinkTesting", "DownloadLinkUpdate"],
    "DalamudApiLevel": ["TestingDalamudApiLevel"],
}

# 保留在修剪后的清单中的键
TRIMMED_KEYS = [
    "Author",
    "Name",
    "Punchline",
    "Description",
    "Changelog",
    "Tags",
    "InternalName",
    "AssemblyVersion",
    "TestingAssemblyVersion",
    "RepoUrl",
    "ApplicableVersion",
    "DalamudApiLevel",
    "IconUrl",
    "ImageUrls",
]


def main():
    # 从 zip 文件中提取插件清单
    master = extract_manifests()

    # 修剪清单以保留必要字段
    master = [trim_manifest(manifest) for manifest in master]

    # 为修剪后的清单添加额外字段
    add_extra_fields(master)

    # 将汇总的清单写入 JSON 文件
    write_master(master)

    # 更新汇总清单中的最后修改时间
    last_update()


def extract_manifests():
    manifests = []

    # 遍历插件目录
    for dirpath, dirnames, filenames in os.walk("./plugins"):
        # 如果存在'testing'目录，则跳过
        if "testing" in dirnames:
            dirnames.remove("testing")
        # 如果没有 zip 文件则继续
        if len(filenames) == 0 or "latest.zip" not in filenames:
            continue

        # 从目录路径中获取插件名称
        plugin_name = dirpath.split("/")[-1]
        latest_zip = f"{dirpath}/latest.zip"

        # 打开最新的 zip 文件并读取清单
        with ZipFile(latest_zip) as z:
            manifest = json.loads(z.read(f"{plugin_name}.json").decode("utf-8"))

            # 检查是否存在测试版本并添加相关信息
            testing_zip_path = f"./plugins/{plugin_name}/testing/latest.zip"
            if os.path.exists(testing_zip_path):
                with ZipFile(testing_zip_path) as tz:
                    testing_manifest = json.loads(
                        tz.read(f"{plugin_name}.json").decode("utf-8")
                    )
                    manifest["TestingAssemblyVersion"] = testing_manifest.get(
                        "AssemblyVersion"
                    )
            manifests.append(manifest)

    return manifests


def add_extra_fields(manifests):
    for manifest in manifests:
        # 生成安装下载链接
        manifest["DownloadLinkInstall"] = DOWNLOAD_URL.format(
            branch=BRANCH, plugin_name=manifest["InternalName"]
        )
        # 如果缺少，则添加默认值
        for k, v in DEFAULTS.items():
            if k not in manifest:
                manifest[k] = v
        # 根据指定创建重复键
        for source, keys in DUPLICATES.items():
            for k in keys:
                if k not in manifest:
                    manifest[k] = manifest[source]
        manifest["DownloadCount"] = 0

        # 如果存在测试版本，则添加测试下载链接
        if "TestingAssemblyVersion" in manifest:
            manifest["DownloadLinkTesting"] = TESTING_DOWNLOAD_URL.format(
                branch=BRANCH, plugin_name=manifest["InternalName"]
            )


def write_master(master):
    # 将主清单作为美化的 JSON 写入文件
    with open("pluginmaster.json", "w") as f:
        json.dump(master, f, indent=4)


def trim_manifest(plugin):
    # 保留清单中必要的字段
    return {k: plugin[k] for k in TRIMMED_KEYS if k in plugin}


def last_update():
    # 加载现有的主清单
    with open("pluginmaster.json", encoding="utf-8") as f:
        master = json.load(f)

    # 更新每个插件的最后修改时间戳
    for plugin in master:
        latest = f'plugins/{plugin["InternalName"]}/latest.zip'
        modified = int(getmtime(latest))

        if "LastUpdate" not in plugin or modified != int(plugin["LastUpdate"]):
            plugin["LastUpdate"] = str(modified)

    # 将更新后的主清单写回文件
    with open("pluginmaster.json", "w", encoding="utf-8") as f:
        json.dump(master, f, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
