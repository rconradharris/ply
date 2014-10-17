import unittest

import plypatch
from plypatch import fixup_patch


class FixupPatchTestCase(unittest.TestCase):
    ORIGINAL = """\
From 15f7e0465065ad2140c0a3bcb45a74cb99763a14 Mon Sep 17 00:00:00 2001
From: Rick Harris <rconradharris@gmail.com>
Date: Mon, 17 Jun 2013 11:35:48 -0500
Subject: Bar

Ply-Patch: foo.patch


diff --git a/README b/README
index bc56c4d..ebd7525 100644
--- a/README
+++ b/README
@@ -1 +1 @@
-Foo
+Bar
-- 
1.8.3.1.245.g39fd762

"""

    def assertLongMatch(self, expected, actual):
        """Assert geared for long strings."""
        self.assert_(expected == actual, "{{%s}}\n\n!=\n\n{{%s}}" % (expected, actual))

    def assertReplacement(self, func, expected, original=None):
        if not original:
            original = self.ORIGINAL

        lines = original.split('\n')
        func(lines)
        actual = '\n'.join(lines)
        self.assertLongMatch(expected, actual)

    def test_fixup_patch(self):
        expected = """\
From ply Mon Sep 17 00:00:00 2001
From: Rick Harris <rconradharris@gmail.com>
Date: Mon, 17 Jun 2013 11:35:48 -0500
Subject: Bar


diff --git a/README b/README
index bc56c4d..ebd7525 100644
--- a/README
+++ b/README
@@ -1 +1 @@
-Foo
+Bar
-- 
1.8.3

"""
        actual = fixup_patch.fixup_patch(self.ORIGINAL)
        self.assertLongMatch(expected, actual)

    def test_replace_from_sha1(self):
        expected = """\
From ply Mon Sep 17 00:00:00 2001
From: Rick Harris <rconradharris@gmail.com>
Date: Mon, 17 Jun 2013 11:35:48 -0500
Subject: Bar

Ply-Patch: foo.patch


diff --git a/README b/README
index bc56c4d..ebd7525 100644
--- a/README
+++ b/README
@@ -1 +1 @@
-Foo
+Bar
-- 
1.8.3.1.245.g39fd762

"""
        self.assertReplacement(fixup_patch._replace_from_sha1,
                               expected)


    def test_replace_git_version(self):
        expected = """\
From 15f7e0465065ad2140c0a3bcb45a74cb99763a14 Mon Sep 17 00:00:00 2001
From: Rick Harris <rconradharris@gmail.com>
Date: Mon, 17 Jun 2013 11:35:48 -0500
Subject: Bar

Ply-Patch: foo.patch


diff --git a/README b/README
index bc56c4d..ebd7525 100644
--- a/README
+++ b/README
@@ -1 +1 @@
-Foo
+Bar
-- 
1.8.3

"""
        self.assertReplacement(fixup_patch._replace_git_version,
                               expected)

    def test_remove_ply_patch_annotation(self):
        expected = """\
From 15f7e0465065ad2140c0a3bcb45a74cb99763a14 Mon Sep 17 00:00:00 2001
From: Rick Harris <rconradharris@gmail.com>
Date: Mon, 17 Jun 2013 11:35:48 -0500
Subject: Bar



diff --git a/README b/README
index bc56c4d..ebd7525 100644
--- a/README
+++ b/README
@@ -1 +1 @@
-Foo
+Bar
-- 
1.8.3.1.245.g39fd762

"""
        self.assertReplacement(fixup_patch._remove_ply_patch_annotation,
                               expected)

    def test_remove_trailing_extra_blank_lines_from_subject(self):
        expected = """\
From 15f7e0465065ad2140c0a3bcb45a74cb99763a14 Mon Sep 17 00:00:00 2001
From: Rick Harris <rconradharris@gmail.com>
Date: Mon, 17 Jun 2013 11:35:48 -0500
Subject: Bar

Ply-Patch: foo.patch

diff --git a/README b/README
index bc56c4d..ebd7525 100644
--- a/README
+++ b/README
@@ -1 +1 @@
-Foo
+Bar
-- 
1.8.3.1.245.g39fd762

"""
        func = fixup_patch._remove_trailing_extra_blank_lines_from_subject
        self.assertReplacement(func, expected)
