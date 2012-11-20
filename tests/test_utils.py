import unittest

from ply import utils


NOT_PRESENT = 'New Feature'
PRESENT = 'New Feature\n\nPly-Patch: mypatch.patch'


class AddPatchAnnotationTests(unittest.TestCase):
    def test_basic(self):
        commit_msg = utils.add_patch_annotation('New Feature', 'mypatch.patch')
        self.assertEqual(PRESENT, commit_msg)


class GetPatchAnnotationTests(unittest.TestCase):
    def test_not_present(self):
        self.assertEqual(None, utils.get_patch_annotation(NOT_PRESENT))

    def test_present(self):
        self.assertEqual('mypatch.patch', utils.get_patch_annotation(PRESENT))


class MakePatchNameTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual('Simple.patch', utils.make_patch_name('Simple'))

    def test_with_space(self):
        self.assertEqual('With-Space.patch',
                         utils.make_patch_name('With Space'))

    def test_odd_chars(self):
        self.assertEqual('There--Their.patch',
                         utils.make_patch_name('There -> Their'))

    def test_with_prefix(self):
        self.assertEqual('prefix/Simple.patch',
                         utils.make_patch_name('Simple', prefix='prefix'))
