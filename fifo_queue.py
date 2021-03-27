class FIFOQueue:
    __slots__ = '_tasks', '_remaining', 'executed', 'executing'

    def __init__(self):
        self._tasks = []
        self._remaining = []
        self.executed = False
        self.executing = False

    def exec(self):
        self.executing = True
        for task in self._tasks:
            self.run(task)
        self.executing = False
        self.executed = True
        self._tasks = self._remaining
        self._remaining = []
        if len(self._tasks) != 0:
            self.exec()

    def append(self, task):
        if self.executing:
            self._remaining.append(task)
        elif not self.executed:
            self._tasks.append(task)
        else:
            self.run(task)  # Should be defined in subclasses
