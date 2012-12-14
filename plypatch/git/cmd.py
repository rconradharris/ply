import contextlib
import functools
import os
import subprocess

from plypatch.git import exc


def add(filename):
    subprocess.check_call(['git', 'add', filename])


def am(*patch_paths, **kwargs):
    three_way_merge = kwargs.get('three_way_merge', False)
    abort = kwargs.get('abort', False)
    resolved = kwargs.get('resolved', False)
    skip = kwargs.get('skip', False)
    quiet = kwargs.get('quiet', False)

    args = ['git', 'am']
    args.extend(patch_paths)

    if three_way_merge:
        args.append('--3way')

    if resolved:
        args.append('--resolved')

    if skip:
        args.append('--skip')

    if abort:
        args.append('--abort')

    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()

    if not quiet:
        print stdout

    if proc.returncode != 0:
        raise exc.PatchDidNotApplyCleanly

    if 'atch already applied' in stdout:
        raise exc.PatchAlreadyApplied


def checkout(branch_name, create=False, create_and_reset=False):
    args = ['git', 'checkout']

    if create and create_and_reset:
        raise exc.MutuallyIncompatibleOptions("create and create_and_reset")

    if create:
        args.append('-b')

    if create_and_reset:
        args.append('-B')

    args.append(branch_name)
    subprocess.check_call(args)


def commit(msg, all=False, amend=False, use_commit_object=None, quiet=False):
    args = ['git', 'commit']

    if msg is not None:
        args.extend(['-m', '%s' % msg])

    if all:
        args.append('-a')

    if amend:
        args.append('--amend')

    if use_commit_object:
        args.extend(['-C', use_commit_object])

    if quiet:
        args.append('-q')

    subprocess.check_call(args)


def config(cmd, config_key=None, config_value=None):
    """Add/unset git configs"""
    args = ['git', 'config']

    if cmd == 'add':
        assert config_key and config_value
        args.extend(['--add', config_key, config_value])
    elif cmd == 'get':
        args.extend(['--get', config_key])
    elif cmd == 'unset':
        args.extend(['--unset', config_key])
    else:
        raise ValueError('unknown command %s' % cmd)

    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise exc.GitException((proc.returncode, stdout, stderr))
    lines = [line.strip() for line in stdout.split('\n') if line]
    return lines


def diff_index(treeish, name_only=False):
    """git diff-index --name-only HEAD --"""
    args = ['git', 'diff-index', treeish]
    if name_only:
        args.append('--name-only')
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise exc.GitException((proc.returncode, stdout, stderr))
    filenames = [line.strip() for line in stdout.split('\n') if line]
    return filenames


def format_patch(since):
    """Returns a list of patch files"""
    args = ['git', 'format-patch', since]

    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise exc.GitException((proc.returncode, stdout, stderr))
    filenames = [line.strip() for line in stdout.split('\n') if line]
    return filenames


def init(directory, quiet=False):
    args = ['git', 'init']
    if quiet:
        args.append('-q')
    args.append(directory)
    subprocess.check_call(args)


def log(cmd_arg=None, count=None, pretty=None, skip=None):
    args = ['git', 'log']
    if pretty:
        args.append("--pretty=%s" % pretty)
    if count is not None:
        args.append("-%d" % count)
    if skip is not None:
        args.append("--skip=%d" % skip)
    if cmd_arg:
        args.append(cmd_arg)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise exc.GitException((proc.returncode, stdout, stderr))
    return stdout


def reset(commit, hard=False, quiet=False):
    args = ['git', 'reset', commit]
    if hard:
        args.append('--hard')
    if quiet:
        args.append('-q')
    subprocess.check_call(args)


def rm(filename, quiet=False):
    args = ['git', 'rm', filename]
    if quiet:
        args.append('-q')
    subprocess.check_call(args)


class Repo(object):
    """Represent a git repo.

    This is a convenience object that saves you from having to manually
    change to the git repo's path before running the specified commands.
    """

    def __init__(self, path):
        self.path = os.path.abspath(path)
        for fname in __cmds__:
            fn = globals()[fname]
            decorated_fn = self._with_temporary_chdir(fn)
            setattr(self, fname, decorated_fn)

    @contextlib.contextmanager
    def chdir(self):
        orig_path = os.getcwd()
        os.chdir(self.path)
        try:
            yield
        finally:
            os.chdir(orig_path)

    def _with_temporary_chdir(self, fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            with self.chdir():
                return fn(*args, **kwargs)
        return wrapper

    def uncommitted_changes(self):
        return len(self.diff_index('HEAD')) != 0


__cmds__ = ['add', 'am', 'checkout', 'commit', 'config', 'diff_index',
            'format_patch', 'init', 'log', 'reset', 'rm']

__all__ = __cmds__ + ['Repo']
