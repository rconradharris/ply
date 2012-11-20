import unittest

from ply import utils


NOT_PRESENT = 'New Feature'
PRESENT = 'New Feature\n\nPly-Patch: mypatch.patch'


class AddPatchAnnotation(unittest.TestCase):
    def test_basic(self):
        commit_msg = utils.add_patch_annotation('New Feature', 'mypatch.patch')
        self.assertEqual(PRESENT, commit_msg)


class GetPatchAnnotation(unittest.TestCase):
    def test_not_present(self):
        self.assertEqual(None, utils.get_patch_annotation(NOT_PRESENT))

    def test_present(self):
        self.assertEqual('mypatch.patch', utils.get_patch_annotation(PRESENT))
