import re

RE_PATCH_IDENTIFIER = re.compile('Ply-Patch: (.*)')


def add_patch_annotation(commit_msg, patch_name):
    """Adds a patch-annotation to a commit msg.

    Returns the modified commit msg.
    """
    return '%s\n\nPly-Patch: %s' % (commit_msg, patch_name)


def get_patch_annotation(commit_msg):
    """Return the Ply-Patch annotation if present in the commit msg.

    Returns None if not present.
    """
    matches = re.search(RE_PATCH_IDENTIFIER, commit_msg)
    if not matches:
        return None

    return matches.group(1)
