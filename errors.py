class DomainError(Exception):
    def __init__(self, message, status=409):
        self.message = message
        self.status = status
        super().__init__(message)
