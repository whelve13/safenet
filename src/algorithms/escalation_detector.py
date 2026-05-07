from collections import deque
from safenet.src.models.message import Message
from safenet.src.models.config import AnalysisConfig

class EscalationDetector:
    def __init__(self, config: AnalysisConfig | None = None):
        self.config = config or AnalysisConfig()
        self.window_size = self.config.escalation_window_size
        self.escalation_threshold = self.config.escalation_sensitivity
        # Stores recent messages per user pair: { (sender_id, receiver_id): deque(maxlen) }
        self.history: dict[tuple[str, str], deque[Message]] = {}

    def _get_queue(self, sender_id: str, receiver_id: str) -> deque[Message]:
        pair = (sender_id, receiver_id)
        if pair not in self.history:
            self.history[pair] = deque(maxlen=self.window_size)
        return self.history[pair]

    def analyze_escalation(self, message: Message) -> bool:
        # If it's a broadcast message, we don't track pair-wise escalation here
        if not message.receiver_id:
            return False

        queue = self._get_queue(message.sender_id, message.receiver_id)
        queue.append(message)

        # We need a full window to confidently detect escalation
        if len(queue) < self.window_size:
            return False

        # Calculate moving averages of the first half vs second half of the window
        midpoint = len(queue) // 2

        first_half_score = sum(msg.toxicity_score for msg in list(queue)[:midpoint]) / midpoint
        second_half_score = sum(msg.toxicity_score for msg in list(queue)[midpoint:]) / (len(queue) - midpoint)

        # If the second half is significantly more toxic than the first half, it's escalating
        if (second_half_score - first_half_score) >= self.escalation_threshold:
            return True

        return False