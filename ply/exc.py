class PlyException(Exception):
    pass


class AlreadyLinkedToPatchRepo(PlyException):
    pass


class PathNotFound(PlyException):
    pass


class UncommittedChanges(PlyException):
    pass
