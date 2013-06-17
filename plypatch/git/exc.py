class GitException(Exception):
    pass


class PatchAlreadyApplied(GitException):
    pass


class PatchDidNotApplyCleanly(GitException):
    pass


class PatchBlobSHA1Invalid(PatchDidNotApplyCleanly):
    pass


class MutuallyIncompatibleOptions(GitException):
    pass
