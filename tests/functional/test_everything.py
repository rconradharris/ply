import os
import re
import shutil
import unittest

import plypatch


class FunctionalTestCase(unittest.TestCase):
    SANDBOX = '.functional-sandbox'
    KEEP_SANDBOX = True

    def setUp(self):
        # Create Sandbox
        if os.path.exists(self.SANDBOX):
            shutil.rmtree(self.SANDBOX)

        os.mkdir(self.SANDBOX)

        # Create PatchRepo
        self.patch_repo_path = os.path.join(self.SANDBOX, 'patch-repo')
        os.mkdir(self.patch_repo_path)
        self.patch_repo = plypatch.PatchRepo(self.patch_repo_path)
        self.patch_repo.initialize()

        # Create WorkingRepo
        self.working_repo_path = os.path.join(self.SANDBOX, 'working-repo')
        os.mkdir(self.working_repo_path)
        self.working_repo = plypatch.WorkingRepo(self.working_repo_path)
        self.working_repo.init('.', quiet=True)
        self.working_repo.link(self.patch_repo_path)

        # Add test-file
        self.readme_path = os.path.join(self.working_repo_path, 'README')
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of there country.',
                          commit_msg='Adding README')
        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.upstream_hash = self.working_repo.log(
            count=1, pretty='%H').strip()

    def tearDown(self):
        if not self.KEEP_SANDBOX:
            shutil.rmtree(self.SANDBOX)

    def assert_readme(self, expected):
        with open(self.readme_path) as f:
            self.assertEqual(expected, f.read())

    def write_readme(self, txt, commit_msg=None):
        with open(self.readme_path, 'w') as f:
            f.write(txt)

        if commit_msg:
            self.working_repo.add('README')
            self.working_repo.commit(commit_msg, quiet=True)

    def test_cant_link_twice(self):
        with self.assertRaises(plypatch.exc.AlreadyLinkedToPatchRepo):
            self.working_repo.link(self.patch_repo_path)

    def test_cant_unlink_if_not_linked(self):
        self.working_repo.unlink()
        self.assertIs(None, self.working_repo.patch_repo_path)
        with self.assertRaises(plypatch.exc.NoLinkedPatchRepo):
            self.working_repo.unlink()

    def test_single_patch__save_and_restore(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)

        self.working_repo.reset('HEAD^', hard=True, quiet=True)

        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.working_repo.restore(quiet=True)

        self.assert_readme('Now is the time for all good men to come to the'
                           ' aid of their country.')

        # Ensure that Ply-Based-On annotation matches upstream hash
        commit_msg = self.patch_repo.log(count=1, pretty='%B').strip()
        based_on = re.search('Ply-Based-On: (.*)', commit_msg).group(1)
        self.assertEqual(self.upstream_hash, based_on)

    def test_two_patches_save_and_restore(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country!',
                          commit_msg='Add exclamation point!')

        self.working_repo.save(self.upstream_hash)

        self.working_repo.reset('HEAD~2', hard=True, quiet=True)

        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.working_repo.restore(quiet=True)

        self.assert_readme('Now is the time for all good men to come to the'
                           ' aid of their country!')

        # Ensure that Ply-Based-On annotation matches upstream hash
        commit_msg = self.patch_repo.log(count=1, pretty='%B').strip()
        based_on = re.search('Ply-Based-On: (.*)', commit_msg).group(1)
        self.assertEqual(self.upstream_hash, based_on)


if __name__ == '__main__':
    unittest.main()
