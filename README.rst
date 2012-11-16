================================
ply - git-based patch management
================================

Description
===========

`ply` is a utility to manage a series of patches against an upstream project.
These patches are stored as files in a separate git repositiory so that they
can themselves be versioned. The patch series is applied in order to create a
branch which can then be used for packaging and deployment.

Concepts
========

The upstream project is housed in the ``upstream-repo`` (UR). This is where
you pull the latest version of the project from.

The patches are stored in the ``patch-repo`` (PR). This is a separate ``git``
repo that contains the patch-files along with the history of the patches as
they've changed over time.

Your local checkout of the upstream repo is the ``working-repo`` (WR) and is
linked to the ``patch-repo`` when ``ply`` is initialized. The ``working-repo``
is where you'll do most of your work: you'll make changes, commit them, and
then generate patches which get saved to the ``patch-repo`` from here.

Design
======

``ply`` is designed with the following goals in mind::

  * Make versioning of patches easy. Minimize the number of steps needed to
    create and refresh patches.

  * Integrate well with ``git``. (Both from a workflow perspective as well as
    using ``git``'s patch management tools under-the-hood)

  * Be simple. Things will go wrong, so this tool is designed to be simple
    enough that you can work through the steps manually to correct any
    mistakes that have occured. (No black-magic!)


Implementation
==============

Under the hood, ``ply`` is built around the ``git format-patch`` and ``git
am`` tools. These are used for generating the patches (diffs plus commit
metadata) and later applying them to , respectively. 

``ply``'s responsibility is
to automate


named-branch (wr)
tag (wr)
commit-hash (wr)



.ply/
  master/
    UPSTREAM_BRANCH=master
    PATCH_BRANCH=patch_repo/master
  qe/
    UPSTREAM_BRANCH=master
    PATCH_BRANCH=patch_repo/master



All configuration is stored in the PR.
WR
  .ply/
    patches-applied
    patch-repo


PR
  .ply/
    config
      [master]




How do we link a patch-repo to a working-repo?
A file called ./ply/patch-repo contains a pointer to the patch repo.

What happens when you change branches with patches applied?


Q. How does ply keep track of which patches have been applied and which still
need applying?

A. Could use a patches-applied file, but that doesn't really match what the git
history says.

Really we should embed a sentinel in the commit msg that indicates which patch
this is:

Patch: rax/cells/patch1.patch

Q. How are patches identified?

A. Patches are identified by a guaranteed unique, slugified form of their name.

Q. How are patches ordered?

A. A `series` files at the base of the patch repo determines the order in which
patches are applied.

Q. What happens if the `series` file and the on-disk patches get out of sync?

A. If there's a missing patch, then `ply` will complain with an error. If an
additional patch is found, but no entry is found in the `series` file, then we
should generate a warning.


Q. I have a separate QE branch that I want to maintain. How do I maintain a
separate set of patches for that branch?

With `ply`, your patches are stored as files in a git repo. This allows you to
branch your patches.

In this case, it would make sense to have a separate branch for the qe patches
which are maintined independently for the life of the qe branch.

You can do all of the usual tricks of cherry-picking to get patches from the
master branch into the qe branch as needed. Just be sure to update the
`series` file.


How can we organize a series file as well:

A
B
C

Apply in order of A, B, C.

Using whitespace indentation, we can define dependencies

A
  B
  C
    D
E





- ply check
  Ensure all patches mentioned in series file are present and that all patches
  present are in the series file.


Ply save, ordinarily just saves the patch to the root of the patch repo. But
you can alternatly specify a path


ply save rax/cells
  THis will put the patch in the rax/cells directory and update the series
  file with that location.



Commands


ply init-patch-repo .
ply init-working-repo <patch-repo>

ply init

ply apply --patch-repo-branch=<default checks for config mapping or looks for branch with same name>
ply apply --resolved
ply apply --skip
ply apply --abort

ply pick # pick commits over into the patch-repo
