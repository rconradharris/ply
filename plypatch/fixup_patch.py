PATCH_GIT_VERSION = '1.8.3'
FROM_SHA1_VALUE = 'ply'


def _replace_from_sha1(lines):
    """The SHA1 on the 'From' line of the patch will differ each time the
    patch file is regenerated. To keep this from causing chatty diffs,
    replace the SHA1 with a hardcoded value.
    """
    for line_idx, line in enumerate(lines):
        if line.startswith('From'):
            break
    else:
        raise Exception("Malformed patch: 'From' not found")

    parts = lines[line_idx].split(' ')
    parts[1] = FROM_SHA1_VALUE

    lines[line_idx] = ' '.join(parts)


def _replace_git_version(lines):
    """The version of git is embedded in the patch which will differ causing
    chatty-diffs and unecessary conflicts.

    It's terribly evil, but hardcoding this is the easiest way to avoid these
    conflicts.
    """
    for reverse_line_idx, line in enumerate(reversed(lines)):
        if not line:
            continue
        if line[0].isdigit() and '.' in line:
            break
    else:
        raise Exception("Malformed patch: Git version not found")

    # The last line counting backwards (0) becomes -(0) - 1 which becomes -1
    # counting foward
    line_idx = -reverse_line_idx - 1
    lines[line_idx] = PATCH_GIT_VERSION


def _remove_ply_patch_annotation(lines):
    match_idxs = []
    for idx, line in enumerate(lines):
        if 'Ply-Patch:' in line:
            match_idxs.append(idx)

    for idx in reversed(match_idxs):
        del lines[idx]


def _remove_trailing_extra_blank_lines_from_subject(lines):
    """Different versions of git will output different amounts of trailing
    whitespace at the end of a subject headers, so we normalize it by only
    allowing a single trailing blank line.
    """
    for idx, line in enumerate(lines):
        if line.startswith('diff --git'):
            break
    else:
        return

    if idx < 2:
        return

    # If we have two blanks above first `diff --git` remove one of them
    if not lines[idx - 1].strip() and not lines[idx - 2].strip():
        del lines[idx - 1]


def fixup_patch(original):
    lines = original.split('\n')

    _replace_from_sha1(lines)
    _replace_git_version(lines)
    _remove_ply_patch_annotation(lines)
    _remove_trailing_extra_blank_lines_from_subject(lines)

    return '\n'.join(lines)
