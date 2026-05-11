import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.models.message import Message
from src.models.user import User
from src.models.alert import Alert, AlertSeverity
from src.models.config import AnalysisConfig
from src.structures.hash_map import HashMap
from src.structures.interaction_graph import InteractionGraph
from src.structures.priority_queue import PriorityQueue
from src.algorithms.toxicity_analyzer import ToxicityAnalyzer
from src.algorithms.escalation_detector import EscalationDetector

class RiskEngine:
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config or AnalysisConfig()

        # we use our custom HashMap to store users (user_id -> User)
        self.users: HashMap[str, User] = HashMap()
        self.graph = InteractionGraph()
        self.toxicity_analyzer = ToxicityAnalyzer(self.config)
        self.escalation_detector = EscalationDetector(self.config)

        # priority queue to always have the highest-risk user at the top
        self.high_risk_queue: PriorityQueue[User] = PriorityQueue()
        self.alerts: list[Alert] = []

    def get_or_create_user(self, user_id: str, username: str = "Unknown") -> User:
        if not self.users.contains(user_id):
            user = User(id=user_id, username=username)
            self.users.put(user_id, user)
        return self.users.get(user_id)

    def process_message(self, message: Message, pre_scored: bool = False):
        # analyze text toxicity if not pre-scored
        if not pre_scored:
            score, _ = self.toxicity_analyzer.analyze_message(message)
        else:
            score = message.toxicity_score

        # update sender stats
        sender = self.get_or_create_user(message.sender_id, message.sender_id)
        sender.increment_messages(message.is_flagged)

        # handle directed messages (graph and escalation)
        if message.receiver_id:
            receiver = self.get_or_create_user(message.receiver_id, message.receiver_id)

            # update Graph
            self.graph.add_interaction(sender.id, receiver.id, score)

            # record victim if highly toxic
            if message.is_flagged:
                sender.add_victim(receiver.id)

            # check for temporal escalation
            is_escalating = self.escalation_detector.analyze_escalation(message)
            if is_escalating:
                self._generate_alert(
                    target_id=sender.id,
                    severity=AlertSeverity.HIGH,
                    reason=f"Toxicity escalating rapidly towards {receiver.id}",
                    msg_id=message.id,
                    timestamp=message.timestamp
                )

            # check for gang-up behavior (Graph analysis)
            if message.is_flagged:
                aggressors = self.graph.find_gang_up_behavior(
                    receiver.id, min_aggressors=self.config.min_gang_up_aggressors
                )
                if sender.id in aggressors and len(aggressors) >= self.config.min_gang_up_aggressors:
                    self._generate_alert(
                        target_id=sender.id,
                        severity=AlertSeverity.CRITICAL,
                        reason=f"Participating in a gang-up attack against {receiver.id}",
                        msg_id=message.id,
                        timestamp=message.timestamp
                    )

        # immediate alert for high toxicity
        if score >= 0.9:
            self._generate_alert(
                target_id=sender.id,
                severity=AlertSeverity.HIGH,
                reason="Sent a severely abusive message",
                msg_id=message.id,
                timestamp=message.timestamp
            )

        # recompute and queue the senders overall risk
        self._recompute_user_risk(sender)

    def process_messages_batch(self, messages: list[Message]):
        # Batch score all messages first
        self.toxicity_analyzer.analyze_messages_batch(messages)
        
        # Then process them sequentially for temporal/graph logic
        for msg in messages:
            self.process_message(msg, pre_scored=True)

    def _recompute_user_risk(self, user: User):

        # base risk from toxicity ratio
        ratio_risk = user.get_toxicity_ratio()

        # add risk based on number of distinct victims (Graph breadth)
        victim_multiplier = min(len(user.victims) * 0.2, 0.5)

        final_risk = min(ratio_risk + victim_multiplier, 1.0)
        user.update_risk_score(final_risk)

        # push to Max-Heap (Priority Queue) if risk is above a threshold
        if final_risk > self.config.high_risk_floor:
            self.high_risk_queue.push(user, final_risk)

    def _generate_alert(self, target_id: str, severity: AlertSeverity, reason: str, msg_id: str, timestamp):
        alert = Alert(
            id=f"ALT-{len(self.alerts)}",
            timestamp=timestamp,
            target_user_id=target_id,
            severity=severity,
            reason=reason,
            context_message_ids=[msg_id]
        )
        self.alerts.append(alert)

    def get_top_offenders(self, n: int = 5) -> list[User]:
        top_users = []
        temp = []

        while not self.high_risk_queue.is_empty() and len(top_users) < n:
            user, priority = self.high_risk_queue.pop()
            if user not in top_users:
                top_users.append(user)
                temp.append((user, priority))

        # restore queue
        for u, p in temp:
            self.high_risk_queue.push(u, p)

        return top_users
