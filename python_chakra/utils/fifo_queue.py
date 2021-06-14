from abc import abstractmethod
from typing import Generic, List, TypeVar


_T = TypeVar("_T")


class FIFOQueue(Generic[_T]):
    __slots__ = '_tasks', '_remaining', 'executed', 'executing'
    _tasks: List[_T]
    _remaining: List[_T]
    executed: bool
    executing: bool

    def __init__(self):
        self._tasks = []
        self._remaining = []
        self.executed = False
        self.executing = False

    def exec(self):
        self.executing = True
        for task in self._tasks:
            # print(repr(self.__class__), "exec", task)
            self.run(task)
        self.executing = False
        self._tasks = self._remaining
        self._remaining = []
        if len(self._tasks) != 0:
            # print(repr(self.__class__), "run", task)
            self.exec()
        self.executed = True

    def append(self, task: _T):
        # print(repr(self.__class__), "append", task)
        if self.executing:
            self._remaining.append(task)
        # elif self.executed:
        #     self.run(task)
        else:
            self._tasks.append(task)

    def clear(self):
        self._tasks.clear()

    @abstractmethod
    def run(self, value: _T):
        """ Should be defined in subclasses """
        pass
