import os
import shutil

import ply
from ply import git


SANDBOX = 'sandbox'


def _create_patch_repo(patch_repo_path):
    _create_directory(patch_repo_path)
    patch_repo = ply.PatchRepo(patch_repo_path)
    patch_repo.initialize()
    return patch_repo


def _assert_text(readme_path, expected):
    with open(readme_path) as f:
        assert f.read() == expected


def _create_working_repo(working_repo_path, patch_repo):
    _create_directory(working_repo_path)
    working_repo = ply.WorkingRepo(working_repo_path)
    working_repo.init('.', quiet=True)

    # Link to patch repo
    os.symlink(patch_repo.path, os.path.join(working_repo.path, '.patch_repo'))

    # Create Typo
    readme_path = os.path.join(working_repo_path, 'README')
    txt = 'Now is the time for all good men to come to the aid of there'\
          ' country.'

    with open(readme_path, 'w') as f:
        f.write(txt)

    working_repo.add('README')
    working_repo.commit('Adding README', quiet=True)

    _assert_text(readme_path, 'Now is the time for all good men to come to'
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
    except ply.git.exc.PatchDidNotApplyCleanly:
        pass

    # Fix typo conflict
    with open(readme_path, 'w') as f:
        new_typo_txt = new_typo_txt.replace('there', 'their')
        f.write(new_typo_txt)

    working_repo.add('README')

    try:
        working_repo.resolve()
    except ply.git.exc.PatchDidNotApplyCleanly:
        pass

    # Fix exclamation point conflict
    with open(readme_path, 'w') as f:
        new_typo_txt = new_typo_txt.replace('country.', 'country!')
        f.write(new_typo_txt)

    working_repo.add('README')

    working_repo.resolve()

    _assert_text(readme_path, 'Now is the time for all good men to come to'
                              ' the aid of their country! Fin.')

    # Add additional line
    with open(readme_path, 'a') as f:
        f.write('\nOne line')

    working_repo.add('README')
    working_repo.commit("Oneline")
    working_repo.save('HEAD^')

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
