import os
import sys

from plypatch import exc, git, utils


def warn(msg, quiet=True):
    if not quiet:
        print >> sys.stderr, 'warning: %s' % msg


class WorkingRepo(git.Repo):
    """Represents our local fork of the upstream repository.

    This is where we will create new patches (save) or apply previous patches
    to create a new patch-branch (restore).
    """
    def _add_patch_annotation(self, patch_name, quiet=True):
        """Add a patch annotation to the last commit."""
        commit_msg = self.log(count=1, pretty='%B')
        if 'Ply-Patch' not in commit_msg:
            commit_msg += '\n\nPly-Patch: %s' % patch_name
            self.commit(commit_msg, amend=True, quiet=quiet)

    def _walk_commit_msgs_backwards(self):
        skip = 0
        while True:
            commit_msg = self.log(count=1, pretty='%B', skip=skip)
            yield commit_msg
            skip += 1

    def _last_upstream_commit_hash(self):
        """Return the hash for the last upstream commit in the repo.

        We use this to annotate patch-repo commits with the version of the
        working-repo they were based off of.
        """
        num_applied = len(list(self._applied_patches()))
        return self.log(count=1, pretty='%H', skip=num_applied).strip()

    def _applied_patches(self):
        """Return a list of patches that have already been applied to this
        branch.

        We figure this out by walking backwards from HEAD until we reach a
        commit without a 'Ply-Patch' commit msg annotation.
        """
        for commit_msg in self._walk_commit_msgs_backwards():
            patch_name = utils.get_patch_annotation(commit_msg)
            if not patch_name:
                break
            yield patch_name

    def _store_patch_files(self, patch_names, filenames):
        """Store a set of patch files in the patch-repo."""
        for patch_name, filename in zip(patch_names, filenames):
            # Ensure destination exists (in case a prefix was supplied)
            dirname = os.path.dirname(patch_name)
            dest_path = os.path.join(self.patch_repo.path, dirname)
            if dirname and not os.path.exists(dest_path):
                os.makedirs(dest_path)

            os.rename(os.path.join(self.path, filename),
                      os.path.join(self.patch_repo.path, patch_name))

            self.patch_repo.add_patch(patch_name)

    def _commit_to_patch_repo(self, commit_msg, quiet=True):
        based_on = self._last_upstream_commit_hash()
        commit_msg += '\n\nPly-Based-On: %s' % based_on
        self.patch_repo.commit(commit_msg, quiet=quiet)

    @property
    def patch_repo_path(self):
        return os.path.join(self.path, '.patch_repo')

    @property
    def patch_repo(self):
        """Return a patch repo object associated with this working repo via
        the `.patch_repo` symlink.
        """
        return PatchRepo(self.patch_repo_path)

    @property
    def _patch_conflict_path(self):
        return os.path.join(self.path, '.patch-conflict')

    def _conflict_file_exists(self):
        return os.path.exists(self._patch_conflict_path)

    def _create_conflict_file(self, patch_name):
        """The conflict-file gives us a way to memorize the patch-name of the
        conflicting patch so that we can apply the patch-annotation after the
        user resolves the conflict.
        """
        with open(self._patch_conflict_path, 'w') as f:
            f.write('%s\n' % patch_name)

    def _teardown_conflict_file(self):
        """Return the patch name from the temporary conflict file."""
        if not os.path.exists(self._patch_conflict_path):
            raise exc.PathNotFound

        with open(self._patch_conflict_path) as f:
            patch_name = f.read().strip()

        os.unlink(self._patch_conflict_path)
        return patch_name

    def _resolve_conflict(self, method, quiet=True):
        """Resolve a conflict using one of the following methods:

            1. Abort
            2. Skip
            3. Resolve
        """
        kwargs = {method: True, 'quiet': quiet}
        self.am(**kwargs)
        return self._teardown_conflict_file()

    def abort(self, quiet=True):
        """Abort a failed merge.

        NOTE: this doesn't rollback commits that have successfully applied.
        """
        self._resolve_conflict('abort', quiet=quiet)
        # Throw away any conflict resolution changes
        self.reset('HEAD', hard=True, quiet=quiet)

    def link(self, patch_repo_path):
        """Link a working-repo to a patch-repo."""
        os.symlink(patch_repo_path, self.patch_repo_path)

    def skip(self, quiet=True):
        """Skip applying current patch and remove from the patch-repo.

        This is useful if the patch is no longer relevant because a similar
        change was made upstream.
        """
        patch_name = self._resolve_conflict('skip', quiet=quiet)

        self.patch_repo.remove_patch(patch_name)
        self.restore(quiet=quiet)  # Apply remaining patches

    def resolve(self, quiet=True):
        """Resolves a commit and refreshes the affected patch in the
        patch-repo.

        Rather than generate a new commit in the patch-repo for each refreshed
        patch, which would make for a rather chatty history, we instead commit
        one time after all of the patches have been applied.
        """
        patch_name = self._resolve_conflict('resolved', quiet=quiet)

        filenames = self.format_patch('HEAD^')
        self._store_patch_files([patch_name], filenames)

        self._add_patch_annotation(patch_name, quiet=quiet)
        self.restore(quiet=quiet)  # Apply remaining patches

    def restore(self, three_way_merge=True, quiet=True):
        """Applies a series of patches to the working repo's current branch.

        Each patch applied creates a commit in the working repo.
        """
        if self.uncommitted_changes():
            raise exc.UncommittedChanges

        applied = set(self._applied_patches())

        for patch_name in self.patch_repo.series:
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
                self.am(patch_path, three_way_merge=three_way_merge,
                        quiet=quiet)
            except git.exc.PatchDidNotApplyCleanly:
                # Memorize the patch-name that caused the conflict so that
                # when we later resolve it, we can add the patch-annotation
                self._create_conflict_file(patch_name)
                raise
            except git.exc.PatchAlreadyApplied:
                self.patch_repo.remove_patch(patch_name)
                warn("Patch '%s' appears to be upstream, removing from"
                     " patch-repo" % patch_name, quiet=False)

            self._add_patch_annotation(patch_name, quiet=quiet)

        # We only commit to the patch-repo when all of the patches in the
        # series have been successfully applied. This minimize chatter in the
        # patch-repo logs.
        if self.patch_repo.uncommitted_changes():
            self._commit_to_patch_repo('Refreshing patches', quiet=quiet)

    def rollback(self, quiet=True):
        """Rollback to that last upstream commit."""
        if self.uncommitted_changes():
            raise exc.UncommittedChanges

        based_on = self._last_upstream_commit_hash()
        self.reset(based_on, hard=True, quiet=quiet)

    def save(self, since, prefix=None, quiet=True):
        """Save a series of commits as patches into the patch-repo."""
        if self.uncommitted_changes():
            raise exc.UncommittedChanges

        if '..' in since:
            raise ValueError(".. not supported at the moment")

        filenames = self.format_patch(since)

        patch_names = []
        for filename in filenames:
            # If commit already has annotation, use that patch-name
            with open(os.path.join(self.path, filename)) as f:
                patch_name = utils.get_patch_annotation(f.read())

            # Otherwise... take it from the `git format-patch` filename
            if not patch_name:
                # Strip 0001- prefix that git format-patch provides. Like
                # `quilt`, `ply` uses a `series` for patch ordering.
                patch_name = filename.split('-', 1)[1]

                # Add our own subdirectory prefix, if needed
                if prefix:
                    patch_name = os.path.join(prefix, patch_name)

            patch_names.append(patch_name)

        self._store_patch_files(patch_names, filenames)

        if len(filenames) > 1:
            commit_msg = "Adding %d patches" % len(filenames)
        else:
            commit_msg = "Adding %s" % patch_name

        self._commit_to_patch_repo(commit_msg, quiet=quiet)

        # Rollback and reapply patches so taht working repo has
        # patch-annotations for latest saved patches
        num_patches = len(self.patch_repo.series)
        self.reset('HEAD~%d' % num_patches, hard=True, quiet=quiet)
        self.restore(quiet=False)

    @property
    def status(self):
        """Return the status of the working-repo."""
        if self._conflict_file_exists():
            return 'restore-in-progress'

        if len(list(self._applied_patches())) == 0:
            return 'no-patches-applied'

        return 'all-patches-applied'

    def check_patch_repo(self):
        return self.patch_repo.check()


class PatchRepo(git.Repo):
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

    def add_patch(self, patch_name):
        self.add(patch_name)

        # Add to series
        if patch_name not in self.series:
            with open(self.series_path, 'a') as f:
                f.write('%s\n' % patch_name)

            self.add('series')

    def remove_patch(self, patch_name):
        self.rm(patch_name)

        # FIXME: read-modify-write here is racey, so lockfile would be useful
        # here.
        with open(self.series_path) as f:
            patch_names = f.read().strip().split('\n')

        patch_names.remove(patch_name)

        with open(self.series_path, 'w') as f:
            for patch_name in patch_names:
                f.write('%s\n' % patch_name)

        self.add('series')

    def initialize(self, quiet=True):
        """Initialize the patch repo (create series file and git-init)."""
        self.init(self.path, quiet=quiet)

        if not os.path.exists(self.series_path):
            with open(self.series_path, 'w') as f:
                pass

            self.add('series')
            self.commit('Ply init', quiet=quiet)

    @property
    def series_path(self):
        return os.path.join(self.path, 'series')

    @property
    def series(self):
        entries = []

        with open(self.series_path, 'r') as f:
            for line in f:
                patch_name = line.strip()
                entries.append(patch_name)

        return entries
