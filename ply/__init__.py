import os

from ply import git


class Repo(object):
    def __init__(self, path):
        self.git_repo = git.Repo(path)

    @property
    def path(self):
        return self.git_repo.path


class WorkingRepo(Repo):
    """Represents our local fork of the upstream repository.

    This is where we will create new patches (save) or apply previous patches
    to create a new patch-branch (restore).
    """
    def format_patches(self, since):
        """Create patch files since a given commmit."""
        filenames = self.git_repo.format_patch(since)

        if not filenames:
            raise Exception('no patch files generated')

        # Remove number prefix from patch filename since we use a `series`
        # file (like quilt) to order the patches
        patch_paths = []
        for filename in filenames:
            orig_path = os.path.join(self.path, filename)
            new_filename = filename.split('-', 1)[1]
            new_path = os.path.join(self.path, new_filename)
            os.rename(orig_path, new_path)

            patch_paths.append(new_path)

        return patch_paths


class PatchRepo(Repo):
    """Represents a git repo containing versioned patch files."""

    def add_patches(self, patch_paths, quiet=True):
        """Adds and commits a set of patches into the patch repo."""
        with open(os.path.join(self.path, 'series'), 'a') as f:
            for orig_patch_path in patch_paths:
                filename = os.path.basename(orig_patch_path)

                patch_path = os.path.join(self.path, filename)
                if os.path.exists(patch_path):
                    name, ext = patch_path.rsplit('.', 1)
                    for dedup in xrange(999):
                        filename = "%s-%d.%s" % (name, dedup + 1, ext)
                        patch_path = os.path.join(self.path, filename)
                        if not os.path.exists(patch_path):
                            break

                os.rename(orig_patch_path, patch_path)
                self.git_repo.add(filename)
                f.write('%s\n' % filename)

        self.git_repo.add('series')

        # TODO: improve this commit msg, for 1 or 2 patches use short form of
        # just comma separated, for more than that, use long-form of number of
        # patches one first-line and filenames enumerated in the body of
        # commit msg.
        self.git_repo.commit('Adding patches', quiet=quiet)


class Ply(object):
    def __init__(self):
        self.working_repo = WorkingRepo('sandbox/working-repo')
        self.patch_repo = PatchRepo('sandbox/patch-repo')

    def save(self, since, quiet=True):
        """Saves a range of commits into the patch-repo.

        1. Create the patches (using `git format-patch`)
        2. Move the patches into the patch-repo (handling any dups)
        3. Update the `series` file in the patch-repo
        4. Commit the new patches
        """
        patch_paths = self.working_repo.format_patches(since)
        self.patch_repo.add_patches(patch_paths, quiet=quiet)


if __name__ == "__main__":
    ply = Ply()
    ply.save('HEAD^1', quiet=True)
