from typing import Any, Generic, TypeVar, Optional

K = TypeVar('K')
V = TypeVar('V')

class HashNode(Generic[K, V]):
    # node for the separate chaining linked list inside the HashMap
    def __init__(self, key: K, value: V):
        self.key = key
        self.value = value
        self.next: Optional['HashNode[K, V]'] = None

class HashMap(Generic[K, V]):
    # custom hash map
    def __init__(self, initial_capacity: int = 16, load_factor_threshold: float = 0.75):
        self.capacity = initial_capacity
        self.size = 0
        self.threshold = load_factor_threshold
        self.buckets: list[Optional[HashNode[K, V]]] = [None] * self.capacity

    def _hash(self, key: K) -> int:
        # computes the bucket index for a given key
        return hash(key) % self.capacity

    def put(self, key: K, value: V) -> None:
        # inserts or updates a key-value pair
        index = self._hash(key)
        head = self.buckets[index]
        
        # check if key already exists, update if so
        current = head
        while current is not None:
            if current.key == key:
                current.value = value
                return
            current = current.next

        # insert new node at the head of the chain
        new_node = HashNode(key, value)
        new_node.next = head
        self.buckets[index] = new_node
        self.size += 1

        # check load factor and resize if necessary
        if self.size / self.capacity > self.threshold:
            self._resize()

    def get(self, key: K) -> Optional[V]:
        # retrieves the value associated with the key, or None if not found
        index = self._hash(key)
        current = self.buckets[index]
        
        while current is not None:
            if current.key == key:
                return current.value
            current = current.next
            
        return None

    def contains(self, key: K) -> bool:
        # checks if a key exists in the hash map
        return self.get(key) is not None

    def remove(self, key: K) -> bool:
        # removes a key-value pair. returns True if removed, False if not found
        index = self._hash(key)
        current = self.buckets[index]
        prev = None
        
        while current is not None:
            if current.key == key:
                if prev is None:
                    self.buckets[index] = current.next
                else:
                    prev.next = current.next
                self.size -= 1
                return True
            prev = current
            current = current.next
            
        return False

    def _resize(self) -> None:
        # doubles the capacity and rehases all existing elements
        old_buckets = self.buckets
        self.capacity *= 2
        self.buckets = [None] * self.capacity
        self.size = 0 # will be recalculated in put()
        
        for head in old_buckets:
            current = head
            while current is not None:
                self.put(current.key, current.value)
                current = current.next

    def keys(self) -> list[K]:
        # returns list of all keys
        key_list = []
        for head in self.buckets:
            current = head
            while current is not None:
                key_list.append(current.key)
                current = current.next
        return key_list

    def values(self) -> list[V]:
        # returns a list of all values
        val_list = []
        for head in self.buckets:
            current = head
            while current is not None:
                val_list.append(current.value)
                current = current.next
        return val_list