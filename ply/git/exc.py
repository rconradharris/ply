class GitException(Exception):
    pass


class PatchAlreadyApplied(GitException):
    pass


class PatchDidNotApplyCleanly(GitException):
    pass


class MutuallyIncompatibleOptions(GitException):
    pass
