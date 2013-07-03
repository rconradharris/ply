import functools
import os
import subprocess
import sys

from plypatch import utils
from plypatch.git import exc


def cmd(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with utils.usedir(self.path):
            return fn(self, *args, **kwargs)
    return wrapper


class Repo(object):
    """Represent a git repo."""

    def __init__(self, path, quiet=False, supress_warnings=False):
        self.path = os.path.abspath(path)
        self.quiet = quiet
        self.supress_warnings = supress_warnings

    def warn(self, msg):
        if not self.supress_warnings:
            print >> sys.stderr, 'warning: %s' % msg

    @cmd
    def add(self, filename):
        subprocess.check_call(['git', 'add', filename])

    @cmd
    def am(self, *patch_paths, **kwargs):
        three_way_merge = kwargs.get('three_way_merge', False)
        abort = kwargs.get('abort', False)
        resolved = kwargs.get('resolved', False)
        skip = kwargs.get('skip', False)
        quiet = kwargs.get('quiet', self.quiet)

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

        proc = subprocess.Popen(args,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        if not quiet:
            print stderr
            print stdout

        if proc.returncode == 0:
            if 'atch already applied' in stdout:
                raise exc.PatchAlreadyApplied
        else:
            if 'sha1 information is lacking or useless' in stderr:
                raise exc.PatchBlobSHA1Invalid
            else:
                raise exc.PatchDidNotApplyCleanly

    @cmd
    def checkout(self, branch_name, create=False, create_and_reset=False):
        args = ['git', 'checkout']

        if create and create_and_reset:
            raise exc.MutuallyIncompatibleOptions(
                'create and create_and_reset')

        if create:
            args.append('-b')

        if create_and_reset:
            args.append('-B')

        args.append(branch_name)
        subprocess.check_call(args)

    # NOTE: clone shouldn't use cmd because directory doesn't exist yet
    def clone(self, path):
        subprocess.check_call(['git', 'clone', path, self.path])

    @cmd
    def commit(self, msg, all=False, amend=False, use_commit_object=None,
               quiet=None):
        if quiet is None:
            quiet = self.quiet

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

    @cmd
    def config(self, cmd, config_key=None, config_value=None):
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

    @cmd
    def diff_index(self, treeish, name_only=False):
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

    @cmd
    def fetch(self, all=False):
        args = ['git', 'fetch']

        if all:
            args.append('--all')

        subprocess.check_call(args)

    @cmd
    def format_patch(self, since, keep_subject=False, no_numbered=False,
                     no_stat=False):
        """Returns a list of patch files"""
        args = ['git', 'format-patch']

        if keep_subject:
            args.append('--keep-subject')

        if no_numbered:
            args.append('--no-numbered')

        if no_stat:
            args.append('--no-stat')

        args.append(since)

        proc = subprocess.Popen(args, stdout=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            raise exc.GitException((proc.returncode, stdout, stderr))
        filenames = [line.strip() for line in stdout.split('\n') if line]
        return filenames

    @cmd
    def init(self, directory, quiet=None):
        if quiet is None:
            quiet = self.quiet

        args = ['git', 'init']

        if quiet:
            args.append('-q')

        args.append(directory)
        subprocess.check_call(args)

    @cmd
    def log(self, cmd_arg=None, count=None, pretty=None, skip=None):
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

    @cmd
    def notes(self, command, message=None):
        args = ['git', 'notes', command]

        if message:
            args.extend(['-m', message])

        subprocess.check_call(args)

    @cmd
    def reset(self, commit, hard=False, quiet=None):
        if quiet is None:
            quiet = self.quiet

        args = ['git', 'reset', commit]

        if hard:
            args.append('--hard')

        if quiet:
            args.append('-q')

        subprocess.check_call(args)

    @cmd
    def rm(self, filename, quiet=None):
        if quiet is None:
            quiet = self.quiet

        args = ['git', 'rm', filename]

        if quiet:
            args.append('-q')

        subprocess.check_call(args)

    def uncommitted_changes(self):
        return len(self.diff_index('HEAD')) != 0

    def rebase_in_progress(self):
        return os.path.exists(os.path.join(self.path, '.git', 'rebase-apply'))
