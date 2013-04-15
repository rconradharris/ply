import os
import re
import shutil
import unittest

import plypatch


class FunctionalTestCase(unittest.TestCase):
    SANDBOX = '.functional-sandbox'
    KEEP_SANDBOX = True
    QUIET = True
    SUPRESS_WARNINGS = True

    def setUp(self):
        # Create Sandbox
        if os.path.exists(self.SANDBOX):
            shutil.rmtree(self.SANDBOX)

        os.mkdir(self.SANDBOX)

        # Create PatchRepo
        self.patch_repo_path = os.path.join(self.SANDBOX, 'patch-repo')
        os.mkdir(self.patch_repo_path)
        self.patch_repo = plypatch.PatchRepo(
            self.patch_repo_path,
            quiet=self.QUIET,
            supress_warnings=self.SUPRESS_WARNINGS)
        self.patch_repo.initialize()

        # Create WorkingRepo
        self.working_repo_path = os.path.join(self.SANDBOX, 'working-repo')
        os.mkdir(self.working_repo_path)
        self.working_repo = plypatch.WorkingRepo(
            self.working_repo_path,
            quiet=self.QUIET,
            supress_warnings=self.SUPRESS_WARNINGS)
        self.working_repo.init('.')
        self.working_repo.link(self.patch_repo_path)

        # Add test-file
        self.readme_path = os.path.join(self.working_repo_path, 'README')
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of there country.',
                          commit_msg='Adding README')
        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.upstream_hash = self.get_working_repo_commit_hash()

    def tearDown(self):
        if not self.KEEP_SANDBOX:
            shutil.rmtree(self.SANDBOX)

    def get_working_repo_commit_hash(self, count=1):
        return self.working_repo.log(count=count, pretty='%H').strip()

    def assert_readme(self, expected):
        with open(self.readme_path) as f:
            self.assertEqual(expected, f.read())

    def write_readme(self, txt, commit_msg=None, mode='w'):
        with open(self.readme_path, mode) as f:
            f.write(txt)

        if commit_msg:
            self.working_repo.add('README')
            self.working_repo.commit(commit_msg)

    def assert_based_on(self, expected):
        commit_msg = self.patch_repo.log(count=1, pretty='%B').strip()
        based_on = re.search('Ply-Based-On: (.*)', commit_msg).group(1)
        self.assertEqual(expected, based_on)

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

        self.working_repo.reset('HEAD^', hard=True)

        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.working_repo.restore()

        self.assert_readme('Now is the time for all good men to come to the'
                           ' aid of their country.')

        self.assert_based_on(self.upstream_hash)
        self.assertEqual('all-patches-applied', self.working_repo.status)

    def test_two_patches_save_and_restore(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country!',
                          commit_msg='Add exclamation point!')

        self.working_repo.save(self.upstream_hash)

        self.working_repo.reset('HEAD~2', hard=True)

        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.working_repo.restore()

        self.assert_readme('Now is the time for all good men to come to the'
                           ' aid of their country!')

        self.assert_based_on(self.upstream_hash)

    def test_upstream_changed(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)
        self.working_repo.reset('HEAD^', hard=True)

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of there country. Fin.',
                          commit_msg='Trunk changed')

        new_upstream_hash = self.working_repo.log(count=1, pretty='%H').strip()

        with self.assertRaises(plypatch.git.exc.PatchDidNotApplyCleanly):
            self.working_repo.restore()

        # Fix conflict
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country. Fin.')
        self.working_repo.add('README')
        self.working_repo.resolve()

        self.assert_based_on(new_upstream_hash)

    def test_rollback(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)

        self.working_repo.rollback()

        self.assert_readme('Now is the time for all good men to come to the'
                           ' aid of there country.')

        self.assertEqual('no-patches-applied', self.working_repo.status)

    def test_uncomitted_change_in_working_repo_cannot_restore(self):
        self.write_readme('Uncomitted change')
        with self.assertRaises(plypatch.exc.UncommittedChanges):
            self.working_repo.restore()

    def test_uncomitted_change_in_patch_repo_cannot_save(self):
        with open(self.patch_repo.series_path, 'a') as f:
            f.write('Uncomitted change')

        with self.assertRaises(plypatch.exc.UncommittedChanges):
            self.working_repo.save('HEAD^')

    def test_merge_patch_upstream_exact_match(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')
        self.working_repo.save(self.upstream_hash)
        self.assertIn('There-Their.patch', self.working_repo.patch_repo.series)
        self.working_repo.rollback()
        self.assertEqual('no-patches-applied', self.working_repo.status)

        # Upstream the patch
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.restore()

        self.assertNotIn('There-Their.patch',
                         self.working_repo.patch_repo.series)
        self.assertNotIn('There-Their.patch',
                         list(self.working_repo._applied_patches()))

        # Since we upstreamed the one-and-only patch, no patches have been
        # applied to the working-repo
        self.assertEqual('no-patches-applied', self.working_repo.status)

    def test_patch_repo_health_check(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.assertEqual(('ok', dict()), self.patch_repo.check())

        # Patch not present in series file
        bogus_path = os.path.join(self.patch_repo.path, 'bogus.patch')
        with open(bogus_path, 'w') as f:
            pass

        expected = ('failed', dict(no_file=set(),
                                   no_series_entry=set(['bogus.patch'])))
        self.assertEqual(expected, self.patch_repo.check())

        os.unlink(bogus_path)

        self.assertEqual(('ok', dict()), self.patch_repo.check())

        # Entry in series file has no corresponding patch file
        with open(self.patch_repo.series_path, 'a') as f:
            f.write('nonexistant.patch\n')

        expected = ('failed', dict(no_file=set(['nonexistant.patch']),
                                   no_series_entry=set([])))
        self.assertEqual(expected, self.patch_repo.check())

    def test_abort(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)
        self.working_repo.rollback()

        self.write_readme('Completely different line.',
                          commit_msg='Upstream changed')

        with self.assertRaises(plypatch.git.exc.PatchDidNotApplyCleanly):
            self.working_repo.restore()

        self.assertEqual('restore-in-progress', self.working_repo.status)

        self.working_repo.abort()

        self.assertEqual('no-patches-applied', self.working_repo.status)

        self.assert_readme('Completely different line.')

    def test_ply_based_on_annotation(self):
        """The Ply-Based-On annotation in the patch repo should always point
        to the commit-hash of the working-repo that reflects the version of
        the upstream code that the patches will apply cleanly to.
        """
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country!',
                          commit_msg='Add exclamation point!')

        self.working_repo.save('HEAD^')

        self.assert_based_on(self.upstream_hash)


if __name__ == '__main__':
    unittest.main()
