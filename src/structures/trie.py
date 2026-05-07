class TrieNode:
    # single node in Trie
    def __init__(self):
        self.children: dict[str, 'TrieNode'] = {}
        self.is_end_of_word: bool = False
        self.weight: float = 0.0


class Trie:
    # Trie (Prefix Tree) data structure
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str, weight: float = 1.0) -> None:
        # inserts a word into the trie
        word = word.lower()
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        
        node.is_end_of_word = True
        node.weight = weight

    def search(self, word: str) -> tuple[bool, float]:
        # searches for a word in the trie, returns tuple
        word = word.lower()
        node = self.root
        for char in word:
            if char not in node.children:
                return False, 0.0
            node = node.children[char]
        
        if node.is_end_of_word:
            return True, node.weight
        return False, 0.0

    def starts_with(self, prefix: str) -> bool:
        # checks if any word in trie starts with given prefix
        prefix = prefix.lower()
        node = self.root
        for char in prefix:
            if char not in node.children:
                return False
            node = node.children[char]
        return True