from cStringIO import StringIO
import unittest

import plypatch


class FixupPatchTestCase(unittest.TestCase):

    def assertLongMatch(self, expected, actual):
        """Assert geared for long strings."""
        self.assert_(expected == actual, "%s\n\n!=\n\n%s" % (expected, actual))

    def test_fixup_patch(self):
        original = """\
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

        from_file = StringIO(original)
        to_file = StringIO()
        plypatch._fixup_patch(from_file, to_file)

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
        to_file.seek(0)
        self.assertLongMatch(expected, to_file.read())
