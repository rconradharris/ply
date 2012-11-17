import os
import shutil

import ply
from ply import git


SANDBOX = 'sandbox'


def _create_working_repo(working_repo_path):
    working_repo = _create_git_repo(working_repo_path)

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
    working_repo.commit('Typofix', quiet=True)

    return working_repo


def _create_directory(path):
    if os.path.exists(path):
        shutil.rmtree(path)

    os.mkdir(path)


def _create_git_repo(path):
    _create_directory(path)
    repo = git.Repo(path)
    repo.init('.', quiet=True)
    return repo


def _create_patch_repo(patch_repo_path):
    _create_directory(patch_repo_path)
    patch_repo = ply.PatchRepo(patch_repo_path)
    patch_repo.init()
    return patch_repo


def main():
    _create_directory(SANDBOX)

    working_repo = _create_working_repo(os.path.join(SANDBOX, 'working-repo'))
    patch_repo = _create_patch_repo(os.path.join(SANDBOX, 'patch-repo'))


if __name__ == '__main__':
    main()
