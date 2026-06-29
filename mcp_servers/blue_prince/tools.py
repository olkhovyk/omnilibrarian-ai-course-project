BLUE_PRINCE_GAME_ID = "blue_prince"


def search_blue_prince_knowledge(*, service, query: str, limit: int = 5) -> dict:
    return {
        "game_id": BLUE_PRINCE_GAME_ID,
        "query": query,
        "results": service.search(game_id=BLUE_PRINCE_GAME_ID, query=query, limit=limit),
    }


def get_blue_prince_entity(*, service, name: str) -> dict:
    return {
        "game_id": BLUE_PRINCE_GAME_ID,
        "name": name,
        "entity": service.get_entity(game_id=BLUE_PRINCE_GAME_ID, name=name),
    }


def search_puzzle_hint(*, service, topic: str, limit: int = 5) -> dict:
    evidence_query = f"Blue Prince puzzle hint {topic}"
    return {
        "game_id": BLUE_PRINCE_GAME_ID,
        "topic": topic,
        "evidence_query": evidence_query,
        "evidence": service.search(game_id=BLUE_PRINCE_GAME_ID, query=evidence_query, limit=limit),
    }
