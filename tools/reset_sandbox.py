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


def _create_working_repo(working_repo_path, patch_repo):
    _create_directory(working_repo_path)
    working_repo = ply.WorkingRepo(working_repo_path)
    working_repo.init('.', quiet=True)

    # Link to patch repo
    os.symlink(patch_repo.path, os.path.join(working_repo.path, '.PATCH_REPO'))

    # Create Typo
    readme_path = os.path.join(working_repo_path, 'README')
    typo_txt = 'Now is the time for all good men to come to the'\
               ' aid of there country.'

    with open(readme_path, 'w') as f:
        f.write(typo_txt)

    working_repo.add('README')
    working_repo.commit('Adding README', quiet=True)

    # Fix Typo
    with open(readme_path, 'w') as f:
        f.write(typo_txt.replace('there', 'their'))

    working_repo.add('README')
    working_repo.commit('There -> Their', quiet=True)
    working_repo.save(prefix='typofixes')

    # Add exclamation point
    with open(readme_path, 'w') as f:
        f.write(typo_txt.replace('.', '!'))

    working_repo.add('README')
    working_repo.commit('Adding exclamation point', quiet=True)
    working_repo.save()

    # Trunk changes
    working_repo.reset('HEAD~2', hard=True, quiet=True)
    with open(readme_path, 'w') as f:
        f.write(typo_txt.replace('.', '. Fin.'))
    working_repo.add('README')
    working_repo.commit('Trunk changed', quiet=True)

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
