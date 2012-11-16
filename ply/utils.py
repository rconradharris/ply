import contextlib
import os

from ply import exceptions


def fixup_path(path):
    path = os.path.expanduser(path)
    path = os.path.abspath(path)
    return path


@contextlib.contextmanager
def temporary_chdir(path):
    if not os.path.exists(path):
        raise exceptions.PathNotFound(path)

    orig_path = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(orig_path)


def read_nearest_file(filename, path):
    file_path = find_file_recursively_to_root(filename, path)
    with open(file_path, 'r') as f:
        return f.read()


def find_file_recursively_to_root(filename, path):
    for cur_path in walk_up_path(path):
        file_path = os.path.join(cur_path, filename)
        if os.path.exists(file_path):
            return file_path
    raise exceptions.PathNotFound


def walk_up_path(path):
    """Walk up a given path towards the root directory.

    For example, path '/a/b/c' would yield:
        /a/b/c
        /a/b
        /a
        /
    """
    prev_path = None
    while True:
        yield path
        prev_path = path
        path, _ = os.path.split(path)
        if prev_path == path:
            raise StopIteration


def write_empty_file(filename):
    return write_file(filename, '')


def write_file(filename, data):
    with open(filename, 'w') as f:
        f.write(data)
