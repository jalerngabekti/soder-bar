from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict

@dataclass
class Order:
    """Represents a single drink order with a timestamp."""
    drink_name: str
    timestamp: datetime

def calculate_popularity_scores(
    orders: List[Order],
    time_window_days: int = 30,
    decay_factor: float = 0.95
) -> Dict[str, float]:
    """
    Calculates popularity scores for drinks based on recent orders.

    A time-decay model is used, where more recent orders contribute more
    to the score. The score for a drink is the sum of the weights of its orders.
    The weight of an order decays exponentially with its age.

    Args:
        orders: A list of Order objects.
        time_window_days: The number of days to consider for the calculation.
                          Orders older than this are ignored.
        decay_factor: The factor by which an order's weight is multiplied
                      for each day of its age. Must be between 0 and 1.
                      A value closer to 1 means slower decay.

    Returns:
        A dictionary mapping drink names to their calculated popularity scores,
        sorted in descending order of popularity.
    """
    if not (0 < decay_factor <= 1):
        raise ValueError("decay_factor must be between 0 (exclusive) and 1 (inclusive).")

    now = datetime.now()
    time_threshold = now - timedelta(days=time_window_days)
    scores = defaultdict(float)

    recent_orders = [order for order in orders if order.timestamp >= time_threshold]

    for order in recent_orders:
        age_in_days = (now - order.timestamp).days
        weight = decay_factor ** age_in_days
        scores[order.drink_name] += weight

    # Sort the results by score in descending order
    sorted_scores = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))

    return sorted_scores
