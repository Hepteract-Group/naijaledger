class FetchRecordNotFoundError(LookupError):
    def __init__(self, fetch_id: str) -> None:
        super().__init__(f"fetch record not found: {fetch_id}")
