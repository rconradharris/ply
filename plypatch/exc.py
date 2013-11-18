class PlyException(Exception):
    pass


class AlreadyLinkedToPatchRepo(PlyException):
    def __init__(self, patch_repo_path=None):
        super(AlreadyLinkedToPatchRepo, self).__init__()
        self.patch_repo_path = patch_repo_path


class AlreadyLinkedToSamePatchRepo(AlreadyLinkedToPatchRepo):
    pass


class AlreadyLinkedToDifferentPatchRepo(AlreadyLinkedToPatchRepo):
    pass


class NoLinkedPatchRepo(PlyException):
    pass


class NoPatchesApplied(PlyException):
    pass


class NothingToResolve(PlyException):
    pass


class PathNotFound(PlyException):
    pass


class UncommittedChanges(PlyException):
    pass


class RestoreInProgress(PlyException):
    pass
