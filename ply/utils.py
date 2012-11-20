import os
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


def make_patch_name(subject, prefix=None):
    """The patch name is a slugified version of the commit msg's first
    line.

    Prefix is an optional subdirectory in the patch-repo where we would
    like to drop our new patch.
    """
    # TODO: add dedup'ing in case patch-file of same name already exists
    # in the patch-repo
    patch_name = ''.join(
            ch for ch in subject if ch.isalnum() or ch == ' ')
    patch_name = patch_name.replace(' ', '-')
    patch_name += '.patch'

    if prefix:
        patch_name = os.path.join(prefix, patch_name)

    return patch_name
