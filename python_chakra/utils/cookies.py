class Cookie:
    def __init__(self) -> None:
        self.last = 0

    def increment(self) -> int:
        last = self.last
        self.last += 1
        return last


cookies = Cookie()
__all__ = "cookies",
