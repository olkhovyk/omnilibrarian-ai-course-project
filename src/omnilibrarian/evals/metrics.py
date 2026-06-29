def accuracy(correct: int, total: int) -> float:
    if total == 0:
        return 0.0
    return correct / total
