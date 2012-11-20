import re
import os

from ply import exc, git


RE_PATCH_IDENTIFIER = re.compile('Ply-Patch: (.*)')


class WorkingRepo(git.Repo):
    """Represents our local fork of the upstream repository.

    This is where we will create new patches (save) or apply previous patches
    to create a new patch-branch (restore).
    """
    def _add_patch_annotation(self, prefix=None, quiet=True):
        """Add a patch annotation to the last commit.

        Prefix is an optional subdirectory in the patch-repo where we would
        like to drop our new patch.
        """
        commit_msg = self.log(count=1, pretty='%B')
        # TODO: add dedup'ing in case patch-file of same name already exists
        # in the patch-repo
        first_line = commit_msg.split('\n')[0]
        patch_name = ''.join(
                ch for ch in first_line if ch.isalnum() or ch == ' ')
        patch_name = patch_name.replace(' ', '-')
        patch_name += '.patch'

        if prefix:
            patch_name = os.path.join(prefix, patch_name)

        commit_msg += '\n\nPly-Patch: %s' % patch_name
        self.commit(commit_msg, amend=True, quiet=quiet)
        return patch_name

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
        return self.log(count=1, pretty='%H', skip=num_applied)

    def _applied_patches(self):
        """Return a list of patches that have already been applied to this
        branch.

        We figure this out by walking backwards from HEAD until we reach a
        commit without a 'Ply-Patch' commit msg annotation.
        """
        for commit_msg in self._walk_commit_msgs_backwards():
            patch_name = self._get_patch_annotation(commit_msg)
            if not patch_name:
                break
            yield patch_name

    def _create_patch(self, patch_name):
        """Create a patch, move it into the patch-repo and add it to the
        series file if necessary.
        """
        # Ensure destination exists (in case a prefix was supplied)
        dirname = os.path.dirname(patch_name)
        if dirname:
            os.makedirs(os.path.join(self.patch_repo.path, dirname))

        filename = self.format_patch('HEAD^')[0]
        os.rename(os.path.join(self.path, filename),
                  os.path.join(self.patch_repo.path, patch_name))
        self.patch_repo.add(patch_name)
        self.patch_repo.add_patch_to_series(patch_name)

    @staticmethod
    def _get_patch_annotation(commit_msg):
        """Return the Ply-Patch annotation if present in the commit msg.

        Returns None if not present.
        """
        matches = re.search(RE_PATCH_IDENTIFIER, commit_msg)
        if not matches:
            return None

        return matches.group(1)

    def _refresh_patch_for_last_commit(self, quiet=True):
        """Refresh the patch in the patch-repo that corresponds to the last
        commit in the working-repo.
        """
        commit_msg = self.log(count=1, pretty='%B')
        patch_name = self._get_patch_annotation(commit_msg)
        self._create_patch(patch_name)

    def _commit_to_patch_repo(self, commit_msg, quiet=True):
        us_hash = self._last_upstream_commit_hash()
        commit_msg += '\n\nPly-Based-On: %s' % us_hash
        self.patch_repo.commit(commit_msg, quiet=quiet)

    @property
    def patch_repo(self):
        """Return a patch repo object associated with this working repo via
        the `.PATCH_REPO` symlink.
        """
        return PatchRepo(os.path.join(self.path, '.PATCH_REPO'))

    def resolve(self, quiet=True):
        """Resolves a commit and refreshes the affected patch in the
        patch-repo.

        Rather than generate a new commit in the patch-repo for each refreshed
        patch, which would make for a rather chatty history, we instead commit
        one time after all of the patches have been applied.
        """
        self.am(resolved=True)
        self._refresh_patch_for_last_commit(quiet=quiet)
        try:
            self.restore()  # Apply remaining patches
        except git.exc.PatchDidNotApplyCleanly:
            raise
        else:
            # Only commit once all of the patches have been applied cleanly
            self._commit_to_patch_repo(
                    'Refreshing patches', quiet=quiet)

    def restore(self, three_way_merge=True):
        """Applies a series of patches to the working repo's current branch.

        Each patch applied creates a commit in the working repo.
        """
        applied = self._applied_patches()

        for patch_name in self.patch_repo.series:
            if patch_name in applied:
                continue

            patch_path = os.path.join(self.patch_repo.path, patch_name)
            self.am(patch_path, three_way_merge=three_way_merge)

    def save(self, prefix=None, quiet=True):
        """Save last commit to working-repo as patch in the patch-repo."""
        patch_name = self._add_patch_annotation(prefix=prefix, quiet=quiet)
        self._create_patch(patch_name)
        self._commit_to_patch_repo('Adding %s' % patch_name, quiet=quiet)


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
