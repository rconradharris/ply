import unittest

from plypatch import utils


class MeaningfulDiffTestCase(unittest.TestCase):
    def test_non_meaningful_diff(self):
        diff_output = """\
--- 0061-Add-support-for-quotas-per-flavor-class.patch  2014-10-14 23:10:02.000000000 -0500
+++ ../nova-rax-patches/Add-support-for-quotas-per-flavor-class.patch   2014-10-14 23:08:42.000000000 -0500
@@ -26 +26 @@
-index 9c36fdf..a5e77a5 100644
+index f003fe4..a8a54b3 100644
@@ -145 +145 @@
-@@ -2491,8 +2519,8 @@ class API(base.Base):
+@@ -2490,8 +2518,8 @@ class API(base.Base):
@@ -156 +156 @@
-@@ -2503,11 +2531,30 @@ class API(base.Base):
+@@ -2502,11 +2530,30 @@ class API(base.Base):
@@ -190 +190 @@
-index dddd8bb..43589b4 100644
+index 83e3ae7..640bef8 100644
@@ -224 +224 @@
-index 8754a65..03fefbd 100644
+index ae79f3c..ea6ed17 100644
@@ -296 +296 @@
-@@ -2919,13 +2972,16 @@ def quota_get_all_by_project_and_user(context, project_id, user_id):
+@@ -2908,13 +2961,16 @@ def quota_get_all_by_project_and_user(context, project_id, user_id):
@@ -316 +316 @@
-@@ -3277,27 +3333,22 @@ def _raise_overquota_exception(project_quotas, user_quotas, deltas, overs,
+@@ -3266,27 +3322,22 @@ def _raise_overquota_exception(project_quotas, user_quotas, deltas, overs,
@@ -360 +360 @@
-@@ -3319,15 +3370,18 @@ def _calculate_overquota(project_quotas, user_quotas, deltas,
+@@ -3308,15 +3359,18 @@ def _calculate_overquota(project_quotas, user_quotas, deltas,
@@ -614 +614 @@
-index a0aa98e..3b42577 100644
+index 870641c..d230d5a 100644
@@ -702 +702 @@
-@@ -2419,12 +2462,16 @@ class _ComputeAPIUnitTestMixIn(object):
+@@ -2413,12 +2456,16 @@ class _ComputeAPIUnitTestMixIn(object):
@@ -721 +721 @@
-index bb67d0c..d9036a9 100644
+index dc13c14..7273178 100644
@@ -724 +724 @@
-@@ -5515,6 +5515,109 @@ class QuotaTestCase(test.TestCase, ModelsObjectComparatorMixin):
+@@ -5514,6 +5514,109 @@ class QuotaTestCase(test.TestCase, ModelsObjectComparatorMixin):
"""
        meaningful = utils.meaningful_diff('notused', 'notused',
                                           diff_output=diff_output)
        self.assertEqual(False, meaningful)

    def test_permissions_changed(self):
        diff_output = """\
-index bb67d0c..d9036a9 100644
+index dc13c14..7273178 100744
"""
        meaningful = utils.meaningful_diff('notused', 'notused',
                                           diff_output=diff_output)
        self.assertEqual(True, meaningful)
