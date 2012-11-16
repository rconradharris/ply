class GitException(Exception):
    pass


class PatchDidNotApplyCleanly(GitException):
    pass


class MutuallyIncompatibleOptions(GitException):
    pass
