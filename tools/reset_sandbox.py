import os
import shutil

import plypatch
from plypatch import git


SANDBOX = 'sandbox'


def _create_patch_repo(patch_repo_path):
    _create_directory(patch_repo_path)
    patch_repo = plypatch.PatchRepo(patch_repo_path)
    patch_repo.initialize()
    return patch_repo


def _assert_text_exact_match(readme_path, expected):
    with open(readme_path) as f:
        assert f.read() == expected


def _assert_text_substring_match(readme_path, expected):
    with open(readme_path) as f:
        assert expected in f.read()


def _create_working_repo(working_repo_path, patch_repo):
    _create_directory(working_repo_path)
    working_repo = plypatch.WorkingRepo(working_repo_path)
    working_repo.init('.', quiet=True)

    # Link to patch repo
    working_repo.link(patch_repo.path)

    # Create Typo
    readme_path = os.path.join(working_repo_path, 'README')
    txt = 'Now is the time for all good men to come to the aid of there'\
          ' country.'

    with open(readme_path, 'w') as f:
        f.write(txt)

    working_repo.add('README')
    working_repo.commit('Adding README', quiet=True)

    _assert_text_exact_match(readme_path,
            'Now is the time for all good men to come to'
            ' the aid of there country.')

    us_hash = working_repo._last_upstream_commit_hash()

    # Fix Typo
    with open(readme_path, 'w') as f:
        f.write(txt.replace('there', 'their'))

    working_repo.add('README')
    working_repo.commit('There -> Their', quiet=True)

    # Add exclamation point
    with open(readme_path, 'w') as f:
        f.write(txt.replace('.', '!'))

    working_repo.add('README')
    working_repo.commit('Adding exclamation point', quiet=True)
    working_repo.save(us_hash)

    # Trunk changes
    working_repo.reset('HEAD~2', hard=True, quiet=True)
    with open(readme_path, 'w') as f:
        new_typo_txt = txt.replace('.', '. Fin.')
        f.write(new_typo_txt)
    working_repo.add('README')
    working_repo.commit('Trunk changed', quiet=True)

    try:
        working_repo.restore(quiet=True)
    except plypatch.git.exc.PatchDidNotApplyCleanly:
        pass

    # Fix typo conflict
    with open(readme_path, 'w') as f:
        new_typo_txt = new_typo_txt.replace('there', 'their')
        f.write(new_typo_txt)

    working_repo.add('README')

    try:
        working_repo.resolve()
    except plypatch.git.exc.PatchDidNotApplyCleanly:
        pass

    # Fix exclamation point conflict
    with open(readme_path, 'w') as f:
        new_typo_txt = new_typo_txt.replace('country.', 'country!')
        f.write(new_typo_txt)

    working_repo.add('README')

    working_repo.resolve()

    _assert_text_exact_match(readme_path,
            'Now is the time for all good men to come to'
            ' the aid of their country! Fin.')

    # Add additional line
    with open(readme_path, 'a') as f:
        f.write('\nOne line')

    working_repo.add('README')
    working_repo.commit("Oneline")
    working_repo.save('HEAD^', quiet=True)

    working_repo.rollback(quiet=True)
    working_repo.restore(quiet=True)

    # Make uncommitted unchange
    with open(readme_path, 'a') as f:
        f.write('Uncommitted change')

    # Ensure uncommitted change is raised
    try:
        working_repo.restore(quiet=True)
    except plypatch.exc.UncommittedChanges:
        pass
    else:
        raise AssertionError('Restore should have failed due to uncommitted'
                              ' changes.')

    working_repo.reset('HEAD', hard=True)

    # Merge 'One line' change upstream.
    # This tests commiting from within the `resolve` operation.
    # We need a separate test for commiting in the `restore` operation.
    assert 'Oneline.patch' in set(working_repo.patch_repo.series)

    working_repo.rollback(quiet=True)

    assert working_repo.status == 'no-patches-applied', working_repo.status

    with open(readme_path, 'a') as f:
        f.write('\nOne line')

    working_repo.add('README')
    working_repo.commit("Merged 'One line' upstream")

    # Fix There -> Their conflict
    try:
        working_repo.restore(quiet=True)
    except plypatch.git.exc.PatchDidNotApplyCleanly:
        pass
    else:
        raise AssertionError('Should have conflicted.')

    assert working_repo.status == 'restore-in-progress', working_repo.status

    fixed_txt = txt + ' Fin.'
    fixed_txt = fixed_txt.replace('there', 'their')

    with open(readme_path, 'w') as f:
        f.write(fixed_txt)
        f.write('\nOne line')

    working_repo.add('README')

    # Fix exclamation point patch
    try:
        working_repo.resolve(quiet=True)
    except plypatch.git.exc.PatchDidNotApplyCleanly:
        pass
    else:
        raise AssertionError('Should have conflicted.')

    fixed_txt = fixed_txt.replace('country.', 'country!')
    with open(readme_path, 'w') as f:
        f.write(fixed_txt)
        f.write('\nOne line')

    working_repo.add('README')
    working_repo.resolve(quiet=True)

    assert 'Oneline.patch' not in set(working_repo.patch_repo.series)

    assert working_repo.status == 'all-patches-applied', working_repo.status

    # Merge upstream exact match and no conflicts so patch-repo commit needs
    # to have been done in the restore method.
    newfile_path = os.path.join(working_repo_path, 'newfile.txt')
    with open(newfile_path, 'w') as f:
        f.write('Newfile\n')

    working_repo.add('newfile.txt')
    working_repo.commit('Adding newfile.txt', quiet=True)
    working_repo.save('HEAD^', quiet=True)

    # Now rollback and merge patch upstream
    working_repo.rollback(quiet=True)

    with open(newfile_path, 'w') as f:
        f.write('Newfile\n')

    working_repo.add('newfile.txt')
    working_repo.commit('Merging newfile.txt upstream', quiet=True)

    working_repo.restore(quiet=True)

    # Test patch-repo health checks
    assert working_repo.patch_repo.check() == ('ok', {})

    bogus_patch_path = os.path.join(
        working_repo.patch_repo.path, 'bogus.patch')

    with open(bogus_patch_path, 'w') as f:
        pass

    assert working_repo.patch_repo.check() == ('failed',
            dict(no_file=set(), no_series_entry=set(['bogus.patch'])))

    os.unlink(bogus_patch_path)
    assert working_repo.patch_repo.check() == ('ok', {})

    # Test abort
    working_repo.rollback()
    with open(readme_path, 'w') as f:
        f.write('')  # Clear README

    working_repo.add('README')
    working_repo.commit("Clearing README file")

    _assert_text_exact_match(readme_path, '')

    try:
        working_repo.restore(quiet=True)
    except plypatch.git.exc.PatchDidNotApplyCleanly:
        pass
    else:
        raise AssertionError('Should have conflicted.')

    working_repo.abort(quiet=True)
    _assert_text_exact_match(readme_path, '')

    # Restore the README since th test passed
    working_repo.reset('HEAD^', hard=True)
    _assert_text_substring_match(readme_path, 'Now is the time')

    return working_repo


def _create_directory(path):
    if os.path.exists(path):
        shutil.rmtree(path)

    os.mkdir(path)


def main():
    _create_directory(SANDBOX)
    patch_repo = _create_patch_repo(os.path.join(SANDBOX, 'patch-repo'))
    working_repo = _create_working_repo(os.path.join(SANDBOX, 'working-repo'),
                                        patch_repo)


if __name__ == '__main__':
    main()
