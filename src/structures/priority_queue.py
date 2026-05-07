from typing import Any, Generic, TypeVar

T = TypeVar('T')

class PQNode(Generic[T]):
    # a node in the priority queue containing the item and its priority
    def __init__(self, item: T, priority: float):
        self.item = item
        self.priority = priority
        
    def __lt__(self, other: 'PQNode[T]') -> bool:
        return self.priority > other.priority

class PriorityQueue(Generic[T]):
    def __init__(self):
        self.heap: list[PQNode[T]] = []

    def _parent(self, index: int) -> int:
        return (index - 1) // 2

    def _left_child(self, index: int) -> int:
        return 2 * index + 1

    def _right_child(self, index: int) -> int:
        return 2 * index + 2

    def _swap(self, i: int, j: int) -> None:
        self.heap[i], self.heap[j] = self.heap[j], self.heap[i]

    def _heapify_up(self, index: int) -> None:
        while index > 0 and self.heap[index] < self.heap[self._parent(index)]:
            self._swap(index, self._parent(index))
            index = self._parent(index)

    def _heapify_down(self, index: int) -> None:
        size = len(self.heap)
        largest = index
        
        while True:
            left = self._left_child(index)
            right = self._right_child(index)
            
            if left < size and self.heap[left] < self.heap[largest]:
                largest = left
            if right < size and self.heap[right] < self.heap[largest]:
                largest = right
                
            if largest == index:
                break
                
            self._swap(index, largest)
            index = largest

    def push(self, item: T, priority: float) -> None:
        # inserts an item into the priority queue
        node = PQNode(item, priority)
        self.heap.append(node)
        self._heapify_up(len(self.heap) - 1)

    def pop(self) -> tuple[T, float]:
        # removes and returns the item with the highest priority
        if self.is_empty():
            raise IndexError("pop from an empty priority queue")
            
        if len(self.heap) == 1:
            node = self.heap.pop()
            return node.item, node.priority
            
        root = self.heap[0]
        self.heap[0] = self.heap.pop()
        self._heapify_down(0)
        
        return root.item, root.priority

    def peek(self) -> tuple[T, float]:
        # returns the highest priority item without removing it
        if self.is_empty():
            raise IndexError("peek from an empty priority queue")
        return self.heap[0].item, self.heap[0].priority

    def is_empty(self) -> bool:
        return len(self.heap) == 0

    def size(self) -> int:
        return len(self.heap)