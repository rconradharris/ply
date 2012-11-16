import os

from ply import git


class Ply(object):
    def __init__(self):
        self.working_repo = git.Repo('sandbox/working-repo')
        self.patch_repo = git.Repo('sandbox/patch-repo')

    def save(self, since, quiet=False, reset=True):
        """save takes a range of commits in the working-repo, creates patch files
        from them, commits those patch files into the patch-repo, and then removes
        the commits from the working repo.
        """
        # Create patch files
        orig_filenames = self.working_repo.format_patch(since)

        if not orig_filenames:
            raise Exception('no patch files generated')

        new_filenames = []

        # Move patch files into patch repo and add to series file
        with open(os.path.join(self.patch_repo.path, 'series'), 'a') as f:
            for orig_filename in orig_filenames:
                orig_path = os.path.join(self.working_repo.path, orig_filename)

                # Remove number prefix from patch filename since we use a `series`
                # file (like quilt) to order the patches
                new_filename = orig_filename.split('-', 1)[1]
                new_path = os.path.join(self.patch_repo.path, new_filename)

                # Dedup any identically named patch files using a suffix
                if os.path.exists(new_path):
                    name, ext = new_filename.rsplit('.', 1)
                    for dedup in xrange(999):
                        new_filename = "%s-%d.%s" % (name, dedup + 1, ext)
                        new_path = os.path.join(self.patch_repo.path, new_filename)
                        if not os.path.exists(new_path):
                            break

                os.rename(orig_path, new_path)
                f.write('%s\n' % new_filename)
                new_filenames.append(new_filename)

        # Commit patch files into patch repo
        for filename in new_filenames:
            self.patch_repo.add(filename)

        self.patch_repo.add('series')

        # TODO: improve this commit msg, for 1 or 2 patches use short form of just
        # comma separated, for more than that, use long-form of number of patches
        # one first-line and filenames enumerated in the body of commit msg.
        self.patch_repo.commit('Adding patches', quiet=quiet)

        # Rollback patches from working-repo
        if reset:
            self.working_repo.reset(since, hard=True, quiet=quiet)

if __name__ == "__main__":
    save('HEAD^1')
