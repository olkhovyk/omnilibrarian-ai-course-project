BG3_GAME_ID = "bg3"


def search_bg3_knowledge(*, service, query: str, limit: int = 5) -> dict:
    return {
        "game_id": BG3_GAME_ID,
        "query": query,
        "results": service.search(game_id=BG3_GAME_ID, query=query, limit=limit),
    }


def get_bg3_entity(*, service, name: str) -> dict:
    return {
        "game_id": BG3_GAME_ID,
        "name": name,
        "entity": service.get_entity(game_id=BG3_GAME_ID, name=name),
    }


def list_bg3_companions(*, service, limit: int = 50) -> dict:
    companions = service.list_entities(game_id=BG3_GAME_ID, content_type="character", limit=limit)
    return {
        "game_id": BG3_GAME_ID,
        "content_type": "character",
        "companions": companions,
        "evidence": [_companion_evidence(companion) for companion in companions],
    }


def compare_bg3_spells(*, service, spell_a: str, spell_b: str, limit: int = 5) -> dict:
    evidence_query = f"Compare {spell_a} and {spell_b} damage range saves scaling"
    return {
        "game_id": BG3_GAME_ID,
        "spell_a": service.get_entity(game_id=BG3_GAME_ID, name=spell_a),
        "spell_b": service.get_entity(game_id=BG3_GAME_ID, name=spell_b),
        "evidence_query": evidence_query,
        "evidence": service.search(game_id=BG3_GAME_ID, query=evidence_query, limit=limit),
    }


def roll_dice(dice_formula: str) -> dict[str, str]:
    return {"dice_formula": dice_formula, "status": "not_implemented"}


def _companion_evidence(companion: dict) -> dict:
    name = companion["canonical_name"]
    return {
        "title": name,
        "section": "Entity registry",
        "source_url": companion["source_url"],
        "text": f"{name} is listed as a Baldur's Gate 3 character or companion entity.",
        "content_type": companion["content_type"],
    }
