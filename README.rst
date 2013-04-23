================================
ply - git-based patch management
================================


Description
===========

``ply`` is a utility to manage a series of patches against an upstream
project.  These patches are stored as files in a separate git repositiory so
that they can themselves be versioned. These patches can then be applied to
create a patched version of the code to be used for packaging and deployment.


Concepts
========

The upstream project resides in the `upstream-repo` (UR). Your local
checkout of the `upstream-repo` is called the `working-repo` and is where
you'll do most of your work: you'll make changes, commit them, and then run
``ply save`` to create a new set of patches, called a `patch-series`.

The patches are stored in the `patch-repo` (PR), a separate ``git`` repo
that is linked to the `working-repo` using the ``ply.patchrepo`` ``git``
config.


Usage
=====

* Initialize a new `patch-repo` which initializes the new ``git`` repo and
  commits an empty ``series`` file::

    ply init .

* Link `working-repo` to a `patch-repo`::

    ply link ../my-patch-repo  # from within the working-repo

* Unlink `working-repo` from current `patch-repo`::

    ply unlink

* Check that status of a `working-repo`::

    ply status
    All patches applied

* Save set of commits to the `patch-repo`::

    # Without --since, any 'new' patches (patches that follow applied patches)
    # will be saved
    ply save

    # Save only the last commit into the 'foo' subdirectory
    ply save --since=HEAD^ --prefix=foo HEAD^

* Rollback `working-repo` to match upstream::

    ply rollback

* Restore `patch-series`::

    ply restore

* Resolve a failed merge and continue applying `patch-series`::

    ply resolve

* Skip a patch that has already merged upstream. In addition to performing a
  ``git am --skip``, this will also remove the relevant patch from the
  `patch-repo`::

        ply skip

  Note: If the upstream patch is an exact match of the version in the
  `patch-repo`, ``ply`` will automatically remove the patch from the
  `patch-repo`.

* Perform a health-check on the `patch-repo`. This ensures that all of the
  patches in the `patch-repo` are accounted for in the `patch-series`::

    ply check
    OK

* Create a `DOT graph <http://en.wikipedia.org/wiki/DOT_language>`_
  representation of patch dependencies::

        ply graph

  The output of this can be piped into ``dot`` to generate a PNG file::

        ply graph | dot -Tpng > dependencies.png


`ply` vs X?
===========

Tools for managing patches have existed for a while, so why create another?

The short answer is:

``quilt`` deals in patch-files which can be versioned but doesn't understand
version-control. This orthogonality, in some respect, is elegant, but is a
hassle in day-to-day use. Why checkpoint files in ``quilt`` when your version
control system already does that for you?

``stgit`` (stacked-git) understands version control but stores patches as
commit objects, not as patch files. This means you can't version your patches,
making it impossible to rollback when things go awry.

``ply`` blends these two tools together to create a tool that understands
version-control but at the same time stores patches as files which can
themselves be versioned.
