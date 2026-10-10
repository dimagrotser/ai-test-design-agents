class MissingApiKey(RuntimeError):
    pass


class IncompleteResponse(RuntimeError):
    def __init__(self, stop_reason: str) -> None:
        super().__init__(f"the model stopped with stop_reason {stop_reason!r}")
        self.stop_reason = stop_reason
