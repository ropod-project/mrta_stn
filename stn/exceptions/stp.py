class NoSTPSolution(Exception):

    def __init__(self):
        """ Raised when the stp solver cannot produce a solution for the problem
        """
        Exception.__init__(self)


class NodeNotFound(Exception):
    def __init__(self):
        """ Raised when attempting to access a node that does not exist"""
