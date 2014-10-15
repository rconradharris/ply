import collections
import contextlib
import os
import re
import shutil
import sys
import tempfile

from plypatch import exc
from plypatch import git
from plypatch import utils
from plypatch import version


__version__ = version.__version__

RE_PATCH_IDENTIFIER = re.compile('Ply-Patch: (.*)')


FROM_SHA1_VALUE = 'ply'
PATCH_GIT_VERSION = '1.8.3'


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
        if line[0].isdigit() and '.' in line:
            break
    else:
        raise Exception("Malformed patch: Git version not found")

    # The last line counting backwards (0) becomes -(0) - 1 which becomes -1
    # counting foward
    line_idx = -reverse_line_idx - 1
    lines[line_idx] = '%s\n' % PATCH_GIT_VERSION


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


def _fixup_patch(from_file, to_file):
    lines = from_file.readlines()
    _replace_from_sha1(lines)
    _replace_git_version(lines)
    _remove_ply_patch_annotation(lines)
    _remove_trailing_extra_blank_lines_from_subject(lines)
    to_file.write(''.join(lines))



class Repo(git.Repo):
    def _add_annotation(self, prefix, value):
        """Add annotation to the last commit."""
        commit_msg = self.log(count=1, pretty='%B')
        if prefix not in commit_msg:
            annotation = '%s: %s' % (prefix, value)
            self.commit(msgs=[commit_msg, annotation], amend=True)


class WorkingRepo(Repo):
    """Represents our local fork of the upstream repository.

    This is where we will create new patches (save) or apply previous patches
    to create a new patch-branch (restore).
    """
    fetch_remotes = True

    def _add_patch_annotation(self, patch_name):
        """Add a patch annotation to the last commit."""
        self._add_annotation('Ply-Patch', patch_name)

    def _get_patch_annotation(self, description):
        """Return the Ply-Patch annotation if present.

        Returns None if not present.
        """
        matches = re.search(RE_PATCH_IDENTIFIER, description)
        if not matches:
            return None

        return matches.group(1)

    def _last_upstream_commit_hash(self):
        """Return the hash for the last upstream commit in the repo.

        We use this to annotate patch-repo commits with the version of the
        working-repo they were based off of.

        The patch before the earliest Ply-Patch annotated commit is the last
        upstream commit.
        """
        applied = self._applied_patches()
        if not applied:
            return None

        last_applied_hash = applied[-1][0]
        return self.log(cmd_arg='%s^' % last_applied_hash,
                        count=1, pretty='%H').strip()

    def _get_commit_hash_and_patch_name(self, cmd_arg=None, count=1,
                                        skip=None):
        value = self.log(cmd_arg, count=count, pretty='%H %B',
                         skip=skip).split(' ', 1)

        if not value[0]:
            return None, None

        commit_hash, description = value
        patch_name = self._get_patch_annotation(description)
        return commit_hash, patch_name

    def _applied_patches(self, new_upper_bound=50):
        """Return a list of patches that have already been applied to this
        branch.

        We can have 3 types of commits, upstream (U), applied (A), and new
        (N), which makes the history look like:

                        UUU...U    ->   AAA...A    ->    NNN..N

        In theory, any number of 'new' commits could exist, meaning we'd
        potentially have to search ALL commits in order to determine if any
        patches have been applied.

        To avoid this costly operation, an upper-bound is given such that if
        we don't find an applied patch within that number of queries, we
        consider no patches as having been applied.
        """
        applied = []

        skip = 0
        while True:
            commit_hash, patch_name = self._get_commit_hash_and_patch_name(
                None, skip=skip)

            skip += 1

            if not commit_hash:
                break

            if patch_name:
                # Patch found, must be within A
                applied.append((commit_hash, patch_name))
            elif applied:
                # Applied patches, but this isn't one: must be at U/A border
                break
            elif new_upper_bound > 0:
                # No applied patches found yet: searching through N
                new_upper_bound -= 1
            else:
                # Exhausted N search, assume no patches applied
                break

        return applied

    @property
    def patch_repo_path(self):
        try:
            path = self.config('get', config_key='ply.patchrepo')[0]
        except git.exc.GitException:
            path = None
        return path

    @property
    def patch_repo(self):
        """Return a patch repo object associated with this working repo via
        the ply.patchrepo git config.
        """
        if not hasattr(self, '_patch_repo'):
            if not self.patch_repo_path:
                raise exc.NoLinkedPatchRepo

            self._patch_repo =  PatchRepo(
                             self.patch_repo_path,
                             quiet=self.quiet,
                             supress_warnings=self.supress_warnings)
        return self._patch_repo

    @property
    def _patch_conflict_path(self):
        return os.path.join(self.path, '.patch-conflict')

    def _create_conflict_file(self, patch_name):
        """The conflict-file gives us a way to memorize the patch-name of the
        conflicting patch so that we can apply the patch-annotation after the
        user resolves the conflict.
        """
        with open(self._patch_conflict_path, 'w') as f:
            f.write('%s\n' % patch_name)

    def _resolve_conflict(self, method):
        """Resolve a conflict using one of the following methods:

            1. Abort
            2. Skip
            3. Resolve
        """
        if not os.path.exists(self._patch_conflict_path):
            raise exc.NothingToResolve

        kwargs = {method: True}
        self.am(**kwargs)

        with open(self._patch_conflict_path) as f:
            patch_name = f.read().strip()

        os.unlink(self._patch_conflict_path)
        return patch_name

    def abort(self):
        """Abort a failed merge.

        NOTE: this doesn't rollback commits that have successfully applied.
        """
        self._resolve_conflict('abort')
        os.unlink(self._restore_stats_path)
        self.rollback(lose_uncommitted=True)

    def link(self, patch_repo_path):
        """Link a working-repo to a patch-repo."""
        patch_repo_path = os.path.abspath(os.path.expanduser(patch_repo_path))

        if not os.path.exists(patch_repo_path):
            raise exc.PathNotFound

        if self.patch_repo_path:
            existing_patch_repo_path = os.path.abspath(
                os.path.expanduser(self.patch_repo_path))

            if os.path.samefile(existing_patch_repo_path, patch_repo_path):
                raise exc.AlreadyLinkedToSamePatchRepo(
                    patch_repo_path=self.patch_repo_path)
            else:
                raise exc.AlreadyLinkedToDifferentPatchRepo(
                    patch_repo_path=self.patch_repo_path)

        self.config('add', config_key='ply.patchrepo',
                    config_value=patch_repo_path)

    def unlink(self):
        """Unlink a working-repo from a patch-repo."""
        if not self.patch_repo_path:
            raise exc.NoLinkedPatchRepo

        self.config('unset', config_key='ply.patchrepo')

    def skip(self):
        """Skip applying current patch and remove from the patch-repo.

        This is useful if the patch is no longer relevant because a similar
        change was made upstream.
        """
        patch_name = self._resolve_conflict('skip')
        self.patch_repo.remove_patch(patch_name)
        self.restore(fetch_remotes=False)  # Apply remaining patches

    def resolve(self):
        """Resolves a commit and refreshes the affected patch in the
        patch-repo.

        Rather than generate a new commit in the patch-repo for each refreshed
        patch, which would make for a rather chatty history, we instead commit
        one time after all of the patches have been applied.
        """
        patch_name = self._resolve_conflict('resolved')
        source_paths, parent_patch_name = self._create_patches('HEAD^')
        if len(source_paths) > 1:
            raise Exception("Too many patches generated")

        self.patch_repo.sync_patches(source_paths, parent_patch_name)

        self._add_patch_annotation(patch_name)
        self.restore(fetch_remotes=False)  # Apply remaining patches

    @property
    def _restore_stats_path(self):
        return os.path.join(self.path, '.restore-stats')

    def _update_restore_stats(self, delta_updated=0, delta_removed=0):
        """Restore-Stats allows us to craft a more useful commit message,
        containing the number of patches updated and removed during a restore.

        The data is stored in a temp file that is cleared when the restore is
        either finished or aborted.

        Diffstat was not used because it is line-oriented as opposed to
        file-oriented. Moreover, a `git log --stat` would provide that info
        already, so the commit msg would be duplicating info.
        """
        updated, removed = self._get_restore_stats()

        updated += delta_updated
        removed += delta_removed

        with open(self._restore_stats_path, 'w') as f:
            f.write('%d %d\n' % (updated, removed))

    def _get_restore_stats(self):
        updated = 0
        removed = 0

        if os.path.exists(self._restore_stats_path):
            with open(self._restore_stats_path, 'r') as f:
                updated, removed = map(int, f.read().strip().split(' '))

        return updated, removed

    def _get_config(self, key):
        try:
            return self.config('get', config_key=key)[0]
        except git.exc.GitException:
            return None

    def _ensure_name_and_email_set(self):
        email = self._get_config('user.email')
        if not email:
            raise exc.GitConfigRequired('user.email')

        name = self._get_config('user.name')
        if not name:
            raise exc.GitConfigRequired('user.name')

    def restore(self, three_way_merge=True, commit_msg=None,
                fetch_remotes=True):
        """Applies a series of patches to the working repo's current
        branch.
        """
        #####################################################################
        #
        #                          Reentrant-Section
        #
        # This bit of code is called repeatedly until all of the patches have
        # been successfully applied, skipped, or we've aborted the restore.
        #
        #####################################################################
        self._ensure_name_and_email_set()

        if self.rebase_in_progress():
            raise exc.RestoreInProgress

        if self.uncommitted_changes():
            raise exc.UncommittedChanges

        if fetch_remotes and self.fetch_remotes:
            self.fetch(all=True)

        applied = set(pn for _, pn in self._applied_patches())
        series = self.patch_repo.series

        total_applied = len(applied)

        for patch_name in series:
            if patch_name in applied:
                continue

            patch_path = os.path.join(self.patch_repo.path, patch_name)

            # Apply from mbox formatted patch, three possible outcomes here:
            #
            # 1. Patch applies cleanly: move on to next patch
            #
            # 2. Patch has conflicts: capture state, bail so user can fix
            #    conflicts
            #
            # 3. Patch was already applied: remove from patch-repo, move on to
            #    next patch
            try:
                self.am(patch_path, three_way_merge=three_way_merge)
            except git.exc.PatchDidNotApplyCleanly:
                # Memorize the patch-name that caused the conflict so that
                # when we later resolve it, we can add the patch-annotation
                self._create_conflict_file(patch_name)
                self._update_restore_stats(delta_updated=1)
                raise
            except git.exc.PatchAlreadyApplied:
                self.patch_repo.remove_patch(patch_name)
                self.warn("Patch '%s' appears to be upstream, removing from"
                          " patch-repo" % patch_name)
                self._update_restore_stats(delta_removed=1)
            else:
                self._add_patch_annotation(patch_name)

            total_applied += 1

            sys.stdout.write('\rRestoring %d/%d' % (total_applied,
                                                    len(series)))
            sys.stdout.flush()

        ######################################################################
        #
        #                              Endgame
        #
        # This bit of code is only reached after all patches have been applied
        # sucessfully or have been skipped. To finish up, we commit any
        # changes we're holding in the patch-repo and peform any necessary
        # housekeeping (removing tempfiles, etc.)
        #
        ######################################################################
        sys.stdout.write('\n')

        updated, removed = self._get_restore_stats()
        if os.path.exists(self._restore_stats_path):
            os.unlink(self._restore_stats_path)

        if not commit_msg:
            commit_msg = 'Refreshing patches: %d updated, %d removed' % (
                updated, removed)

        # Commit to patch repo
        if not self.patch_repo.uncommitted_changes():
            return
        based_on = self._last_upstream_commit_hash()
        self.patch_repo.commit(msgs=[commit_msg])
        self.patch_repo._add_annotation('Ply-Based-On', based_on)

    def rollback(self, lose_uncommitted=False):
        """Rollback to that last upstream commit."""
        if self.uncommitted_changes() and not lose_uncommitted:
            raise exc.UncommittedChanges

        based_on = self._last_upstream_commit_hash()

        if based_on:
            # If any patches successfully applied, roll them back
            self.reset(based_on, hard=True)
        else:
            # If no patches applied successfully applied, then just trash the
            # in-progress changes
            self.reset('HEAD', hard=True)

    def _create_patches(self, since):
        """
        The default output of format-patch isn't ideally suited for our
        purposes since it contains extraneous info as well as text that
        changes even if the underlying patch doesn't change.

        The following options are used to correct this:

        --keep-subject - remove unecessary [PATCH] prefix
        --no-stat - remove unecessary diffstat
        --no-numbered - remove number of patches in set from subject line

        In addition, we need to rewrite the first-line of the patch-file to
        remove an unecessary commit-hash. On refresh, this would change even
        if the actual patch was the same, leading to very noisy diffs.
        """
        filenames = self.format_patch(
            since, keep_subject=True, no_numbered=True, no_stat=True)

        # Rewrite first-line 'From <commit-hash>' -> 'From ply'
        source_paths = []
        for filename in filenames:
            from_path = os.path.join(self.path, filename)
            with tempfile.NamedTemporaryFile(delete=False) as to_file:
                with open(from_path) as from_file:
                    _fixup_patch(from_file, to_file)

            # Strip 0001- prefix that git-format-patch uses
            source_path = os.path.join(self.path, filename.split('-', 1)[1])
            shutil.move(to_file.name, source_path)
            os.unlink(from_path)

            source_paths.append(source_path)

        parent_patch_name = self._get_commit_hash_and_patch_name(
            since)[1]

        return source_paths, parent_patch_name

    def save(self, since=None):
        """Save a series of commits as patches into the patch-repo."""
        if self.uncommitted_changes() or self.patch_repo.uncommitted_changes():
            raise exc.UncommittedChanges

        if not since:
            since = self._last_upstream_commit_hash()

        if not since:
            raise exc.NoPatchesApplied

        if '..' in since:
            raise ValueError(".. not supported at the moment")

        source_paths, parent_patch_name = self._create_patches(since)

        added, updated, skipped, removed = self.patch_repo.sync_patches(
            source_paths, parent_patch_name)

        # Rollback and reapply patches so that working repo has
        # patch-annotations for latest saved patches
        num_patches = len(self.patch_repo.series)
        self.reset('HEAD~%d' % num_patches, hard=True)

        commit_msg = "Saving patches: added %d, updated %d, removed %d" % (
            len(added), len(updated), len(removed))

        # We have to commit to the patch-repo AFTER rolling-back and
        # reapplying so that we have the patch-annotations necessary to figure
        # out the correct Ply-Based-On annotation in the patch-repo.
        self.restore(commit_msg=commit_msg, fetch_remotes=False)

    @property
    def status(self):
        """Return the status of the working-repo."""
        if os.path.exists(self._patch_conflict_path):
            return 'restore-in-progress'

        if len(self._applied_patches()) == 0:
            return 'no-patches-applied'

        return 'all-patches-applied'

    def check_patch_repo(self):
        return self.patch_repo.check()


class PatchRepo(Repo):
    """Represents a git repo containing versioned patch files."""

    def check(self):
        """Sanity check the patch-repo.

        This ensures that the number of patches in the patch-repo matches the
        series file.
        """
        series = set(self.series)
        patch_names = set(self.patch_names)

        # Has entry in series file but not actually present
        no_file = series - patch_names

        # Patch files exists, but no entry in series file
        no_series_entry = patch_names - series

        if not no_file and not no_series_entry:
            return ('ok', {})

        return ('failed', dict(no_file=no_file,
                               no_series_entry=no_series_entry))

    @property
    def patch_names(self):
        """Return all patch files in the patch-repo (recursively)."""
        patch_names = []
        # Strip base path so that we end up with relative paths against the
        # patch-repo making the results `patch_names`
        strip = self.path + '/'
        for path in utils.recursive_glob(self.path, '*.patch'):
            patch_names.append(path.replace(strip, ''))
        return patch_names

    @contextlib.contextmanager
    def _mutate_series_file(self):
        """The series file is effectively a list of patches to apply in order.
        This function allows you to add/remove/reorder the patches in the
        series-file by manipulating a plain-old Python list.
        """
        # FIXME: mutate_series_file doesn't support recursive series files yet
        # Read in series file and create list
        patch_names = self._non_recursive_series(self.series_path)

        # Allow caller to mutate it
        yield patch_names

        # Write back new contents
        with open(self.series_path, 'w') as f:
            for patch_name in patch_names:
                f.write('%s\n' % patch_name)

        self.add('series')

    def _determine_what_changed(self, source_paths, parent_patch_name):
        added = set()
        updated = set()
        skipped = set()

        for source_path in source_paths:
            patch_name = os.path.basename(source_path)
            dest_path = os.path.join(self.path, patch_name)
            if utils.path_exists_case_sensitive(dest_path):
                # For simplicity, we regenerate all patches, however some will
                # be the same, so perform a file compare so we keep accurate
                # counts of which were truly updatd
                if utils.meaningful_diff(source_path, dest_path):
                    updated.add(patch_name)
                else:
                    skipped.add(patch_name)
            else:
                added.add(patch_name)

        # Skip all patches up to parent_patch_name
        if parent_patch_name:
            patch_names = self._non_recursive_series(self.series_path)
            for patch_name in patch_names:
                skipped.add(patch_name)
                if patch_name == parent_patch_name:
                    break

        series = set(self.series)
        removed = series - added - updated - skipped

        return added, updated, skipped, removed

    def sync_patches(self, source_paths, parent_patch_name):
        """Sync patches into working repo, adding, updating, and removing
        patches as necessary.

        `patches` is a list of tuples representing `patch_name` and
        `source_path`.

        `parent_patch_name` represents where in the `series` file we should
        insert the new patch set.

        `None` indicates that the patch-set doesn't have a parent so it should
        be inserted at the beginning of the series file.
        """
        added, updated, skipped, removed = self._determine_what_changed(
                source_paths, parent_patch_name)

        source_lookup = {}
        dest_lookup = {}
        for source_path in source_paths:
            patch_name = os.path.basename(source_path)
            source_lookup[patch_name] = source_path
            dest_lookup[patch_name] = os.path.join(self.path, patch_name)

        # Toss the skipped patches
        for patch_name in skipped:
            if patch_name in source_lookup:
                os.unlink(source_lookup[patch_name])

        # Remove any patches that should no longer be present
        for patch_name in removed:
            self.rm(patch_name, force=True)

        # Move the added and updated patches
        for patch_name in added | updated:
            shutil.move(source_lookup[patch_name],
                        dest_lookup[patch_name])
            self.add(patch_name)

        # Update series file
        with self._mutate_series_file() as entries:
            for patch_name in removed:
                entries.remove(patch_name)

            if parent_patch_name:
                base = entries.index(parent_patch_name) + 1
            else:
                base = 0

            for idx, source_path in enumerate(source_paths):
                patch_name = os.path.basename(source_path)
                if patch_name in entries:
                    # Already exists, reorder patch by removing it from
                    # current location and inserting it into the new location.
                    entries.remove(patch_name)

                entries.insert(base + idx, patch_name)

        return added, updated, skipped, removed

    def remove_patch(self, patch_name):
        with self._mutate_series_file() as entries:
            # If there were any local changes and it's not in the series
            # file, we still want to remove it, hence force=True
            self.rm(patch_name, force=True)
            entries.remove(patch_name)

    def initialize(self):
        """Initialize the patch repo (create series file and git-init)."""
        self.init(self.path)

        if not os.path.exists(self.series_path):
            with open(self.series_path, 'w') as f:
                pass

            self.add('series')
            self.commit(msgs=['Ply init'])

    @property
    def series_path(self):
        return os.path.join(self.path, 'series')

    def _non_recursive_series(self, series_path):
        patch_names = []

        with open(series_path) as f:
            for line in f:
                line = line.strip()

                if not line:
                    continue

                patch_names.append(line)

        return patch_names

    def _recursive_series(self, series_path):
        """Emit patch_names from series file, handling -i recursion."""
        for patch_name in self._non_recursive_series(series_path):
            if not patch_name.startswith('-i '):
                yield patch_name
                continue

            # If entry starts with -i, what follows is a path to a
            # child series file
            series_rel_path = patch_name.split(' ', 1)[1].strip()
            child_series_path = os.path.join(
                self.path, series_rel_path)
            patch_dir = os.path.dirname(series_rel_path)
            for child_patch_name in self._recursive_series(
                    child_series_path):
                yield os.path.join(patch_dir, child_patch_name)

    @property
    def series(self):
        return list(self._recursive_series(self.series_path))

    def _changed_files_for_patch(self, patch_name):
        """Returns a set of files that were modified by specified patch."""
        changed_files = set()
        patch_path = os.path.join(self.path, patch_name)
        with open(patch_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith('--- a/'):
                    line = line.replace('--- a/', '')
                elif line.startswith('+++ b/'):
                    line = line.replace('+++ b/', '')
                else:
                    continue
                filename = line
                if filename.startswith('/dev/null'):
                    continue
                changed_files.add(filename)

        return changed_files

    def _changes_by_filename(self):
        """Return a breakdown of what patches modifiied a given file over the
        whole patch series.

        {filename: [patch1, patch2, ...]}
        """
        file_changes = collections.defaultdict(list)
        for patch_name in self.series:
            changed_files = self._changed_files_for_patch(patch_name)
            for filename in changed_files:
                file_changes[filename].append(patch_name)

        return file_changes

    def patch_dependencies(self):
        """Returns a graph representing the file-dependencies between patches.

        To retiterate, this is not a call-graph representing
        code-dependencies, this is a graph representing how files change
        between patches, useful in breaking up a large patch set into smaller,
        independent patch sets.

        The graph uses patch_names as nodes with directed edges representing
        files that both patches modify. In Python:

            {(dependent, parent): set(file_both_touch1, file_both_touch2, ...)}
        """
        graph = collections.defaultdict(set)
        for filename, patch_names in self._changes_by_filename().iteritems():
            parent = None
            for dependent in patch_names:
                if parent:
                    graph[(dependent, parent)].add(filename)
                parent = dependent
        return graph

    def patch_dependency_dot_graph(self):
        """Return a DOT version of the dependency graph."""
        lines = ['digraph patchdeps {']

        for (dependent, parent), changed_files in\
                self.patch_dependencies().iteritems():
            label = ', '.join(sorted(changed_files))
            lines.append('"%s" -> "%s" [label="%s"];' % (
                dependent, parent, label))

        lines.append('}')
        return '\n'.join(lines)
