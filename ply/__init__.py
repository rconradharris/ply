import os

from ply import exc, git, utils


class WorkingRepo(git.Repo):
    """Represents our local fork of the upstream repository.

    This is where we will create new patches (save) or apply previous patches
    to create a new patch-branch (restore).
    """
    def _add_patch_annotation(self, patch_name, quiet=True):
        """Add a patch annotation to the last commit."""
        commit_msg = self.log(count=1, pretty='%B')
        commit_msg = utils.add_patch_annotation(commit_msg, patch_name)
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

    def _create_patch(self, patch_name, revision):
        """Create a patch, move it into the patch-repo and add it to the
        series file if necessary.
        """
        # Ensure destination exists (in case a prefix was supplied)
        dirname = os.path.dirname(patch_name)
        dest_path = os.path.join(self.patch_repo.path, dirname)
        if dirname and not os.path.exists(dest_path):
            os.makedirs(dest_path)

        filenames = self.format_patch('%s^..%s' % (revision, revision))
        assert len(filenames) == 1
        filename = filenames[0]

        os.rename(os.path.join(self.path, filename),
                  os.path.join(self.patch_repo.path, patch_name))
        self.patch_repo.add(patch_name)
        self.patch_repo.add_patch_to_series(patch_name)

    def _commit_to_patch_repo(self, commit_msg, based_on, quiet=True):
        commit_msg += '\n\nPly-Based-On: %s' % based_on
        self.patch_repo.commit(commit_msg, quiet=quiet)

    @property
    def patch_repo(self):
        """Return a patch repo object associated with this working repo via
        the `.patch_repo` symlink.
        """
        return PatchRepo(os.path.join(self.path, '.patch_repo'))

    @property
    def _patch_conflict_path(self):
        return os.path.join(self.path, '.patch-conflict')

    def _teardown_conflict_file(self):
        """Return the patch name from the temporary conflict file.

        This is needed so we can add a patch-annotation after resolving a
        conflict.
        """
        if not os.path.exists(self._patch_conflict_path):
            raise exc.PathNotFound

        with open(self._patch_conflict_path) as f:
            patch_name = f.read().strip()

        os.unlink(self._patch_conflict_path)
        return patch_name

    def resolve(self, quiet=True):
        """Resolves a commit and refreshes the affected patch in the
        patch-repo.

        Rather than generate a new commit in the patch-repo for each refreshed
        patch, which would make for a rather chatty history, we instead commit
        one time after all of the patches have been applied.
        """
        self.am(resolved=True, quiet=quiet)
        patch_name = self._teardown_conflict_file()
        self._create_patch(patch_name, 'HEAD')
        self._add_patch_annotation(patch_name, quiet=quiet)

        try:
            self.restore()  # Apply remaining patches
        except git.exc.PatchDidNotApplyCleanly:
            raise
        else:
            # Only commit once all of the patches have been applied cleanly
            based_on = self._last_upstream_commit_hash()
            self._commit_to_patch_repo(
                    'Refreshing patches', based_on, quiet=quiet)

    def restore(self, three_way_merge=True, quiet=True):
        """Applies a series of patches to the working repo's current branch.

        Each patch applied creates a commit in the working repo.
        """
        applied = set(self._applied_patches())

        for patch_name in self.patch_repo.series:
            if patch_name in applied:
                continue

            patch_path = os.path.join(self.patch_repo.path, patch_name)

            try:
                self.am(patch_path, three_way_merge=three_way_merge,
                        quiet=quiet)
            except git.exc.PatchDidNotApplyCleanly:
                # Memorize the patch-name that caused the conflict so that
                # when we later resolve it, we can add the patch-annotation
                with open(self._patch_conflict_path, 'w') as f:
                    f.write('%s\n' % patch_name)

                raise

            self._add_patch_annotation(patch_name, quiet=quiet)

    def save(self, since='HEAD^', prefix=None, quiet=True):
        """Save last commit to working-repo as patch in the patch-repo."""
        cmd_arg = "%s..HEAD" % since
        commits = [x.split(' ', 1) for x in self.log(
                   cmd_arg=cmd_arg, pretty='%H %s').split('\n') if x]
        commits.reverse()
        for revision, subject in commits:
            patch_name = utils.make_patch_name(subject, prefix=prefix)
            self._create_patch(patch_name, revision)

        # Rollback and reapply so that the current branch of working-repo has
        # the patch-annotations in its history. Annotations are created on
        # application of patch not on creation. This makes it easier to
        # support saving multiple patches as well as making it easier to
        # rename and move patches in the patch repo, since the name isn't
        # embedded in the patch itself.

        # Rollback unannotated patches
        self.reset(since, hard=True, quiet=quiet)

        # Rollback annotated patches
        num_applied = len(list(self._applied_patches()))
        self.reset('HEAD~%d' % num_applied, hard=True, quiet=quiet)

        based_on = self.log(count=1, pretty='%H')

        if len(commits) > 1:
            commit_msg = "Adding %d patches" % len(commits)
        else:
            commit_msg = "Adding %s" % patch_name

        self._commit_to_patch_repo(commit_msg, based_on, quiet=quiet)

        # Hiding the output of this command because it would be confusing,
        # it's an implementation detail that we have to rollback-and-reapply
        # patches to put the working-repo into the proper state.
        self.restore(quiet=True)


class PatchRepo(git.Repo):
    """Represents a git repo containing versioned patch files."""
    def add_patch_to_series(self, patch_name):
        if patch_name not in self.series:
            with open(self.series_path, 'a') as f:
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
        with open(self.series_path, 'r') as f:
            for line in f:
                patch_name = line.strip()
                yield patch_name
