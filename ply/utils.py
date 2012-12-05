import fnmatch
import os
import re


RE_PATCH_IDENTIFIER = re.compile('Ply-Patch: (.*)')


def get_patch_annotation(commit_msg):
    """Return the Ply-Patch annotation if present in the commit msg.

    Returns None if not present.
    """
    matches = re.search(RE_PATCH_IDENTIFIER, commit_msg)
    if not matches:
        return None

    return matches.group(1)


def recursive_glob(path, glob):
    """Glob against a directory recursively.

    Modified from: http://stackoverflow.com/questions/2186525/
        use-a-glob-to-find-files-recursively-in-python
    """
    matches = []
    for root, dirnames, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, glob):
            matches.append(os.path.join(root, filename))
    return matches
