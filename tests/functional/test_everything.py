import glob
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
        self.patch_repo = self._create_patch_repo(self.patch_repo_path)

        # Create WorkingRepo
        self.working_repo_path = os.path.join(self.SANDBOX, 'working-repo')
        self.working_repo = self._create_working_repo(self.working_repo_path)

        # Add test-file
        self.readme_path = os.path.join(self.working_repo_path, 'README')
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of there country.',
                          commit_msg='Adding README')
        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.upstream_hash = self.working_repo.get_head_commit_hash()

    def _create_patch_repo(self, path):
        os.mkdir(path)
        patch_repo = plypatch.PatchRepo(
                path, quiet=self.QUIET,
                supress_warnings=self.SUPRESS_WARNINGS)
        patch_repo.initialize()
        return patch_repo

    def _create_working_repo(self, path):
        os.mkdir(path)
        working_repo = plypatch.WorkingRepo(
                path, quiet=self.QUIET,
                supress_warnings=self.SUPRESS_WARNINGS)
        working_repo.init('.')
        working_repo.link(self.patch_repo_path)
        return working_repo

    def tearDown(self):
        if not self.KEEP_SANDBOX:
            shutil.rmtree(self.SANDBOX)

    def assert_readme(self, expected):
        with open(self.readme_path) as f:
            self.assertEqual(expected, f.read())

    def write_readme(self, txt, commit_msg=None, mode='w'):
        with open(self.readme_path, mode) as f:
            f.write(txt)

        if commit_msg:
            self.working_repo.add('README')
            self.working_repo.commit(msgs=[commit_msg])

    def assert_based_on(self, expected):
        commit_msg = self.patch_repo.log(count=1, pretty='%B').strip()
        based_on = re.search('Ply-Based-On: (.*)', commit_msg).group(1)
        self.assertEqual(expected, based_on)

    def test_already_linked_same_repo(self):
        with self.assertRaises(plypatch.exc.AlreadyLinkedToSamePatchRepo):
            self.working_repo.link(self.patch_repo_path)

    def test_already_linked_different_repo(self):
        with self.assertRaises(plypatch.exc.AlreadyLinkedToDifferentPatchRepo):
            self.working_repo.link('/bin')

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

        new_upstream_hash = self.working_repo.get_head_commit_hash()

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
        #
        # This test was randomly failing due to the way git works; the
        # solution was to add the [HASHHACK] suffix to the commit msg.
        #
        # The reason the test would fail is that the downstream and upstream
        # commit objects would (sometimes) be commited within the same
        # second, due to how fast the test runs, causing them to receive the
        # same commit hash.
        #
        # Since they shared the same commit hash, the second, upstream commit
        # would erroneously share the git-notes from the first, downstream
        # commit object, which caused the test to fail.
        #
        # The solution is to either sleep (which slows the test), or to modify
        # the commit msg so that the commit-object hashes to a different
        # value.
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their [HASHHACK]')

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

    def test_abort_no_patch_successfully_applied(self):
        """If we abort and no other patches were successfully applied, then we
        should end up back at the last-upstream hash naturally by just
        throwing away the conflicting patch.
        """
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)
        self.working_repo.rollback()

        self.write_readme('Completely different line.',
                          commit_msg='Upstream changed')

        new_upstream_hash = self.working_repo.get_head_commit_hash()

        with self.assertRaises(plypatch.git.exc.PatchDidNotApplyCleanly):
            self.working_repo.restore()

        self.assertEqual('restore-in-progress', self.working_repo.status)

        self.working_repo.abort()

        self.assertEqual('no-patches-applied', self.working_repo.status)

        self.assert_readme('Completely different line.')

        self.assertEqual(new_upstream_hash,
                         self.working_repo.get_head_commit_hash())

    def test_abort_patch_successfully_applied(self):
        """If we abort after a successfully applied patch, then we must
        rollback in order to be back at the last-upstream-hash.
        """
        self.write_readme('A\nB\nC', commit_msg='Adding A, B, and C')
        new_upstream_hash = self.working_repo.get_head_commit_hash()

        self.write_readme('a\nB\nC', commit_msg='A -> a')
        self.write_readme('a\nb\nC', commit_msg='B -> b')
        self.write_readme('a\nb\nc', commit_msg='C -> c')

        self.working_repo.save(new_upstream_hash)
        self.working_repo.rollback()

        self.write_readme('A\nB\nD', commit_msg='Upstream changed: C -> D')

        newer_upstream_hash = self.working_repo.get_head_commit_hash()

        with self.assertRaises(plypatch.git.exc.PatchDidNotApplyCleanly):
            self.working_repo.restore()

        self.assertEqual('restore-in-progress', self.working_repo.status)

        self.working_repo.abort()

        self.assertEqual('no-patches-applied', self.working_repo.status)

        self.assert_readme('A\nB\nD')

        self.assertEqual(newer_upstream_hash,
                         self.working_repo.get_head_commit_hash())

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

        commit_msg = self.patch_repo.log(cmd_arg='HEAD^', pretty='%B')

        # '[s]aving' should be in commit msg, not 'refreshing'
        self.assertIn('aving', commit_msg)

    def test_save_no_since_supplied(self):
        """A `save` without a `since` argument is a shortcut for save
        <upstream-hash>.

        If no patches have been applied, then `save` without `since` should
        raise an exception.
        """
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)
        self.assert_based_on(self.upstream_hash)
        self.assertEqual(
            self.upstream_hash, self.working_repo._last_upstream_commit_hash())

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country!',
                          commit_msg='Add exclamation point!')

        self.working_repo.save()

        self.working_repo.rollback()

        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of there country.')

        self.working_repo.restore()

        self.assert_readme('Now is the time for all good men to come to'
                           ' the aid of their country!')

    def test_restore_stats_for_new_patch(self):
        self.assertEqual([], glob.glob(os.path.join(self.working_repo.path,
                                                    '*.patch')))

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        self.working_repo.save(self.upstream_hash)

        self.assertEqual([], glob.glob(os.path.join(self.working_repo.path,
                                                    '*.patch')))

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country!',
                          commit_msg='Add exclamation point!')

        self.assertEqual([], glob.glob(os.path.join(self.working_repo.path,
                                                    '*.patch')))

        self.working_repo.save()

        commit_msg = self.patch_repo.log(count=1, pretty='%B').strip()

        expected = 'Saving patches: added 1, updated 0, removed 0'
        self.assertIn(expected, commit_msg)

        # Ensure that we cleaned up any patch-files that weren't moved in to
        # the patch-repo because they were exact matches (filecmp=True)
        self.assertEqual([], glob.glob(os.path.join(self.working_repo.path,
                                                    '*.patch')))

    def test_blob_missing(self):
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country.',
                          commit_msg='There -> Their')

        # Create second repo cloned from first
        working_repo2_path = os.path.join(self.SANDBOX, 'working-repo2')
        working_repo2 = plypatch.WorkingRepo(
                working_repo2_path, quiet=self.QUIET,
                supress_warnings=self.SUPRESS_WARNINGS)

        with plypatch.utils.usedir(self.SANDBOX):
            working_repo2.clone('working-repo')

        working_repo2.link(self.patch_repo_path)

        # Make an upstream change in repo and refresh patches
        #
        # NOTE: This part is same as test_upstream_changed
        self.working_repo.save(self.upstream_hash)
        self.working_repo.reset('HEAD^', hard=True)

        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of there country. Fin.',
                          commit_msg='Trunk changed')

        with self.assertRaises(plypatch.git.exc.PatchDidNotApplyCleanly):
            self.working_repo.restore()

        # Fix conflict and
        self.write_readme('Now is the time for all good men to come to the'
                          ' aid of their country. Fin.')
        self.working_repo.add('README')
        self.working_repo.resolve()

        # If we're not careful here, working_repo2 won't have the blob from
        # working_repo, so the three-way merge won't work. We need to perform
        # a `git fetch --all` to lessen this risk
        with self.assertRaises(
                plypatch.git.exc.PatchDidNotApplyCleanly) as cm:
            working_repo2.restore()

        self.assertNotEqual('PatchBlobSHA1Invalid',
                            cm.exception.__class__.__name__)

    def test_restore_after_conflict_should_raise_restore_in_progress(self):
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

        with self.assertRaises(plypatch.exc.RestoreInProgress):
            self.working_repo.restore()


if __name__ == '__main__':
    unittest.main()
