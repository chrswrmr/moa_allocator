class DSLValidationError(Exception):
    def __init__(self, node_id: str, node_name: str, message: str) -> None:
        self.node_id = node_id
        self.node_name = node_name
        self.message = message
        super().__init__(f"node_id='{node_id}' name='{node_name}' — {message}")


class PriceDataError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
