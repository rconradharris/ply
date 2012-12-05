================================
ply - git-based patch management
================================


Description
===========

`ply` is a utility to manage a series of patches against an upstream project.
These patches are stored as files in a separate git repositiory so that they
can themselves be versioned. These patches can then be applied to create a
patched version of the code to be used for packaging and deployment.


Concepts
========

The upstream project resides in the `upstream-repo` (UR). Your local
checkout of the `upstream-repo` is called the `working-repo` and is where
you'll do most of your work: you'll make changes, commit them, and then run
``ply save`` to create a new set of patches, called a `patch-series`.

The patches are stored in the `patch-repo` (PR), a separate ``git`` repo
that is linked to the `working-repo` by way of a symlink.


Usage
=====

* Initialize a new `patch-repo` which initializes the new ``git`` repo and
  commits an empty ``series`` file::

    ply init .

* Link a `working-repo` to a patch repo::

    ply link ../my-patch-repo  # from within the working-repo

* Check that status of a `working-repo`::

    ply status
    All patches applied

* Save the last commit as a new patch in the `patch-repo`::

    ply save        # Without arguments, HEAD^ is assumed

    # Explicit since argument, saves into `foo` subdirectory in the patch-repo
    ply save --prefix=foo HEAD^

* Rollback `working-repo` to match upstream::

    ply rollback

* Restore `patch-series`::

    ply restore

* Resolve a failed merge and continue applying `patch-series`::

    ply restore --resolved

* Skip a patch that has already merged upstream. In addition to performing a
  `git am --skip`, this will also remove the relevant patch from the
  `patch-repo`::

        ply restore --skip

   Note: If the upstream patch is an exact match of the version in the
   patch-repo, `ply` will automatically remove the patch from the patch-repo.

* Perform a health-check on the patch-repo::

    ply check
    OK
