class DocumentNotFoundError(LookupError):
    def __init__(self, document_id: str) -> None:
        super().__init__(f"document not found: {document_id}")
