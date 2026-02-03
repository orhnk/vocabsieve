from datetime import datetime as dt
import glob
import os
from ..global_names import logger


def get_uniques(l: list):
    return list(set(l) - set([""]))


def uniq_preserve_order(l: list) -> list:
    return sorted(set(l), key=lambda x: l.index(x))


def date_to_timestamp(datestr: str):
    return dt.strptime(datestr, "%Y-%m-%d %H:%M:%S").timestamp()


def find_koreader_settings_dirs(path):
    roots = list(path) if isinstance(path, (list, tuple, set)) else [path]
    roots = [r for r in roots if r]
    settings_dirs = []
    for root in roots:
        # If user selected settings dir directly
        if os.path.basename(root) == "settings" and os.path.exists(os.path.join(root, "lookup_history.lua")):
            settings_dirs.append(root)
            continue

        # Common KOReader locations
        candidates = [
            os.path.join(root, ".koreader", "settings"),
            os.path.join(root, ".addons", "koreader", "settings"),
            os.path.join(root, "koreader", "settings"),
            os.path.join(root, "KOReader", "settings"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                settings_dirs.append(candidate)

    # Directly search for known files and add their parent folders
    for root in roots:
        for file_path in glob.glob(os.path.join(root, "**/lookup_history.lua"), recursive=True):
            settings_dirs.append(os.path.dirname(file_path))
        for file_path in glob.glob(os.path.join(root, "**/vocabulary_builder.sqlite3"), recursive=True):
            settings_dirs.append(os.path.dirname(file_path))

    # Fallback: search for settings directories that contain known files
    if not settings_dirs:
        for root in roots:
            for candidate in glob.glob(os.path.join(root, "**/settings"), recursive=True):
                if os.path.exists(os.path.join(candidate, "lookup_history.lua")) or \
                        os.path.exists(os.path.join(candidate, "vocabulary_builder.sqlite3")):
                    settings_dirs.append(candidate)

    return uniq_preserve_order(settings_dirs)


def findDBpath(path) -> str:
    # KOReader settings may be in a hidden directory
    roots = list(path) if isinstance(path, (list, tuple, set)) else [path]
    roots = [r for r in roots if r]
    settings_dirs = find_koreader_settings_dirs(roots)
    paths = []
    for root in settings_dirs + roots:
        paths += glob.glob(os.path.join(root, "**/vocabulary_builder.sqlite3"), recursive=True)
        paths += glob.glob(os.path.join(root, ".*/**/vocabulary_builder.sqlite3"), recursive=True)
    if paths:
        return paths[0]
    else:
        raise FileNotFoundError("Cannot find vocabulary_builder.sqlite3")


def koreader_scandir(path):
    paths = list(path) if isinstance(path, (list, tuple, set)) else [path]
    filelist = []
    for root in paths:
        if not root:
            continue
        for filetype in ["epub", "fb2", "fb2.zip", "pdf"]:
            files = glob.glob(os.path.join(root, "**/*." + filetype), recursive=True)
            for filename in files:
                if os.path.exists(os.path.join(os.path.dirname(filename),
                                               filename.removesuffix(filetype) + "sdr",
                                               "metadata." + filetype.split(".")[-1] + ".lua")):
                    filelist.append(filename)
    filelist = uniq_preserve_order(filelist)
    logger.info(f"Found {len(filelist)} book files in {', '.join([p for p in paths if p])}: {filelist}")
    return filelist


def findHistoryPath(path):
    # KOReader settings may be in a hidden directory
    roots = list(path) if isinstance(path, (list, tuple, set)) else [path]
    roots = [r for r in roots if r]
    settings_dirs = find_koreader_settings_dirs(roots)
    paths = []
    for root in settings_dirs + roots:
        paths += glob.glob(os.path.join(root, "**/lookup_history.lua"), recursive=True)
        paths += glob.glob(os.path.join(root, ".*/**/lookup_history.lua"), recursive=True)
    if paths:
        return paths[0]
    else:
        return ""
