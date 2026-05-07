from collections import deque
from typing import Optional

class InteractionGraph:
    # directed graph representing interactions between users
    def __init__(self):
        # adjacency list representation - { user_id: { target_id: weight } }
        self.adj_list: dict[str, dict[str, float]] = {}

    def add_node(self, user_id: str) -> None:
        # adds a user to the graph if they don't already exist
        if user_id not in self.adj_list:
            self.adj_list[user_id] = {}

    def add_interaction(self, sender_id: str, receiver_id: str, toxicity_weight: float = 1.0) -> None:
        # adds or updates a directed edge from sender to receiver
        self.add_node(sender_id)
        self.add_node(receiver_id)
        
        # if edge already exists, increase its weight, otherwise create it
        if receiver_id in self.adj_list[sender_id]:
            self.adj_list[sender_id][receiver_id] += toxicity_weight
        else:
            self.adj_list[sender_id][receiver_id] = toxicity_weight

    def get_targets(self, sender_id: str) -> dict[str, float]:
        # returns all users targeted by the sender, along with the interaction weight
        return self.adj_list.get(sender_id, {})

    def find_gang_up_behavior(self, target_id: str, min_aggressors: int = 2) -> list[str]:
        # detects if multiple distinct users are targeting the same user with toxic messages
        aggressors = []
        for node, edges in self.adj_list.items():
            if target_id in edges and edges[target_id] > 0:
                aggressors.append(node)
                
        if len(aggressors) >= min_aggressors:
            return aggressors
        return []

    def bfs_toxicity_spread(self, start_user_id: str, weight_threshold: float = 1.0) -> set[str]:
        # uses bfs to find the network of users affected by a specific toxic user
        if start_user_id not in self.adj_list:
            return set()
            
        visited = set()
        queue = deque([start_user_id])
        visited.add(start_user_id)
        
        affected_network = set()
        
        while queue:
            current_user = queue.popleft()
            targets = self.adj_list.get(current_user, {})
            
            for target_user, weight in targets.items():
                if target_user not in visited and weight >= weight_threshold:
                    visited.add(target_user)
                    affected_network.add(target_user)
                    queue.append(target_user)
                    
        return affected_network