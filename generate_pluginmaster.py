import json
import os
from time import time
from sys import argv
from os.path import getmtime
from zipfile import ZipFile, ZIP_DEFLATED

BRANCH = os.environ['GITHUB_REF'].split('refs/heads/')[-1]
DOWNLOAD_URL = 'https://github.com/NiGuangOwO/DalamudPlugins/raw/{branch}/plugins/{plugin_name}/latest.zip'

DEFAULTS = {
    'IsHide': False,
    'IsTestingExclusive': False,
    'ApplicableVersion': 'any',
}

DUPLICATES = {
    'DownloadLinkInstall': ['DownloadLinkTesting', 'DownloadLinkUpdate'],
}

TRIMMED_KEYS = [
    'Author',
    'Name',
    'Punchline',
    'Description',
    'Changelog',
    'InternalName',
    'AssemblyVersion',
    'RepoUrl',
    'ApplicableVersion',
    'Tags',
    'DalamudApiLevel',
    'IconUrl',
    'ImageUrls',
]

def main():
    # extract the manifests from inside the zip files
    master = extract_manifests()

    # trim the manifests
    master = [trim_manifest(manifest) for manifest in master]

    # convert the list of manifests into a master list
    add_extra_fields(master)

    # write the master
    write_master(master)

    # update the LastUpdate field in master
    last_update()

def extract_manifests():
    manifests = []

    for dirpath, dirnames, filenames in os.walk('./plugins'):
        if len(filenames) == 0 or 'latest.zip' not in filenames:
            continue
        plugin_name = dirpath.split('/')[-1]
        latest_zip = f'{dirpath}/latest.zip'
        with ZipFile(latest_zip) as z:
            manifest = json.loads(z.read(f'{plugin_name}.json').decode('utf-8'))
            manifests.append(manifest)

    return manifests

def add_extra_fields(manifests):
    for manifest in manifests:
        # generate the download link from the internal assembly name
        manifest['DownloadLinkInstall'] = DOWNLOAD_URL.format(branch=BRANCH, plugin_name=manifest["InternalName"])
        # add default values if missing
        for k, v in DEFAULTS.items():
            if k not in manifest:
                manifest[k] = v
        # duplicate keys as specified in DUPLICATES
        for source, keys in DUPLICATES.items():
            for k in keys:
                if k not in manifest:
                    manifest[k] = manifest[source]
        manifest['DownloadCount'] = 0

def write_master(master):
    # write as pretty json
    with open('pluginmaster.json', 'w') as f:
        json.dump(master, f, indent=4)

def trim_manifest(plugin):
    return {k: plugin[k] for k in TRIMMED_KEYS if k in plugin}

def last_update():
    with open('pluginmaster.json', encoding='utf-8') as f:
        master = json.load(f)

    for plugin in master:
        latest = f'plugins/{plugin["InternalName"]}/latest.zip'
        modified = int(getmtime(latest))

        if 'LastUpdate' not in plugin or modified != int(plugin['LastUpdate']):
            plugin['LastUpdate'] = str(modified)

    with open('pluginmaster.json', 'w', encoding='utf-8') as f:
        json.dump(master, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()