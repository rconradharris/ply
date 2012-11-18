import re
import os

from ply import exc, git


RE_PATCH_IDENTIFIER = re.compile('Ply-Patch: (.*)')


class Repo(object):
    def __init__(self, path):
        self.git_repo = git.Repo(path)

    @property
    def path(self):
        return os.path.abspath(self.git_repo.path)


class WorkingRepo(Repo):
    """Represents our local fork of the upstream repository.

    This is where we will create new patches (save) or apply previous patches
    to create a new patch-branch (restore).
    """
    def applied_patches(self):
        """Return a list of patches that have already been applied to this
        branch.
        """
        applied = []
        skip = 0
        while True:
            commit_msg = self.git_repo.log(count=1, pretty='%B', skip=skip)
            matches = re.search(RE_PATCH_IDENTIFIER, commit_msg)
            if not matches:
                break

            patch_name = matches.group(1)
            applied.append(patch_name)
            skip += 1

        return applied

    def apply_patches(self, base_path, patch_names, three_way_merge=True):
        """Applies a series of patches to the working repo's current branch.

        Each patch applied creates a commit in the working repo.
        """
        applied = self.applied_patches()

        for patch_name in patch_names:
            if patch_name in applied:
                continue

            patch_path = os.path.join(base_path, patch_name)
            self.git_repo.am(patch_path, three_way_merge=three_way_merge)


    def rollback(self):
        """Rollback the entire patch-set making the branch match upstream."""
        self.git_repo.reset('HEAD~%d' % len(self.applied_patches()), hard=True)

    @property
    def config_path(self):
        return os.path.join(self.path, '.ply')

    @property
    def patch_repo_link_path(self):
        return os.path.join(self.config_path, 'PATCH_REPO')

    @property
    def patch_repo_path(self):
        with open(self.patch_repo_link_path) as f:
            return f.read().strip()

    @property
    def patch_repo(self):
        return PatchRepo(self.patch_repo_path)

    def link_to_patch_repo(self, path, force=False):
        """Link the working-repo to a local copy of the patch-repo."""
        path = os.path.abspath(path)

        if not os.path.exists(self.config_path):
            os.mkdir(self.config_path)

        if os.path.exists(self.patch_repo_link_path) and not force:
            raise exc.AlreadyLinkedToPatchRepo

        if not os.path.exists(path):
            raise exc.PathNotFound

        with open(self.patch_repo_link_path, 'w') as f:
            f.write(path)

    def restore(self, three_way_merge=True):
        patch_names = self.patch_repo.get_patch_names()
        self.apply_patches(self.patch_repo.path, patch_names)

    def save(self, since, quiet=True):
        """Save last commit to working-repo as patch in the patch-repo.

        1. Create the patches (using `git format-patch`)
        2. Move the patches into the patch-repo (handling any dups)
        3. Update the `series` file in the patch-repo
        4. Commit the new patches
        5. Rollback and reapply the patches. This is needed so that the
           commits in the working-repo have the patch id annotation in the
           commit msg which tells ply not to reapply the patch.
        """
        commit_msg = self.git_repo.log(count=1, pretty='%B')

        # Generate patch_name (slugify then add .patch extension)
        first_line = commit_msg.split('\n')[0]
        first_line = first_line.replace(' ', '-')
        patch_name = ''.join(
                ch for ch in first_line if ch.isalnum() or ch == '-')
        patch_name += '.patch'

        # Add patch-name annotation to commit msg (if we're refreshing an
        # existing patch, then the annotation will already be present)
        new = False
        if 'Ply-Patch' not in commit_msg:
            new = True
            commit_msg += '\n\nPly-Patch: %s' % patch_name
            self.git_repo.commit(commit_msg, amend=True)

        # Create patch file
        filename = self.git_repo.format_patch('HEAD^')[0]
        orig_path = os.path.join(self.path, filename)
        new_path = os.path.join(self.path, patch_name)
        os.rename(orig_path, new_path)

        # Add to patch repo
        self.patch_repo.add_patch(new_path, quiet=quiet, new=new)

    def resolve(self):
        """Resolves a commit and refreshes the affected patch in the
        patch-repo.
        """
        # 1. Mark resolved
        self.git_repo.am(resolved=True)

        # 2. Refresh the patch by saving the new version to the patch-repo
        self.save('HEAD^')

        # 3. Apply remaining patches
        self.restore()


class PatchRepo(Repo):
    """Represents a git repo containing versioned patch files."""
    @property
    def series_path(self):
        return os.path.join(self.path, 'series')

    def add_patch(self, orig_patch_path, quiet=True, new=True):
        """Adds and commits a set of patches into the patch repo."""
        # NOTE: if we support saving directly into subdirectories in
        # the patch-repo, then the patch-name won't be the filename,
        # but will be the relative-path + the filename, e.g.
        # private/cells/database-modifications.patch.
        filename = os.path.basename(orig_patch_path)
        patch_path = os.path.join(self.path, filename)
        os.rename(orig_patch_path, patch_path)
        self.git_repo.add(filename)

        if new:
            with open(self.series_path, 'a') as f:
                f.write('%s\n' % filename)
            self.git_repo.add('series')

        # TODO: improve this commit msg, for 1 or 2 patches use short form of
        # just comma separated, for more than that, use long-form of number of
        # patches one first-line and filenames enumerated in the body of
        # commit msg.
        self.git_repo.commit('Adding patches', quiet=quiet)

    def get_patch_names(self):
        with open(self.series_path, 'r') as f:
            for line in f:
                patch_name = line.strip()
                yield patch_name

    def init(self):
        """Initialize the patch repo.

        This performs a git init, adds the series file, and then commits it.
        """
        self.git_repo.init(self.path)

        if not os.path.exists(self.series_path):
            with open(self.series_path, 'w') as f:
                pass

            self.git_repo.add('series')
            self.git_repo.commit('Ply init')


if __name__ == "__main__":
    working_repo = WorkingRepo('sandbox/working-repo')
    working_repo.save('HEAD~1', quiet=False)
    #print working_repo.applied_patches()
