from __future__ import annotations

from dataclasses import dataclass
import re

from omnilibrarian.rag.query_rewriting import rewrite_query


@dataclass(frozen=True)
class ToolSpec:
    game_id: str
    name: str
    intent: str
    entity_content_type: str | None = None
    min_entities: int = 2
    limit: int = 5
    trigger_terms: tuple[str, ...] = ()
    result_argument_name: str | None = None


@dataclass(frozen=True)
class ToolSelection:
    tool: str
    arguments: dict


DEFAULT_TOOL_SPECS = [
    ToolSpec(
        game_id="bg3",
        name="compare_bg3_spells",
        intent="comparison",
        entity_content_type="spell",
        result_argument_name="spell",
    ),
    ToolSpec(
        game_id="bg3",
        name="list_bg3_companions",
        intent="list",
        entity_content_type="character",
        min_entities=0,
        limit=50,
        trigger_terms=(
            "companions",
            "companion",
            "party members",
            "origin characters",
            "list companions",
            "all companions",
            "компаньйони",
            "компаньйонів",
            "супутники",
            "супутників",
            "персонажі в групі",
        ),
    ),
    ToolSpec(
        game_id="blue_prince",
        name="search_puzzle_hint",
        intent="hint",
        min_entities=0,
        limit=5,
        trigger_terms=(
            "hint",
            "hints",
            "puzzle",
            "puzzles",
            "solve",
            "solution",
            "clue",
            "stuck",
            "spoiler",
            "how do i",
            "what should i do",
            "help me with",
            "підказка",
            "підказки",
            "підказку",
            "головоломка",
            "головоломки",
            "головоломку",
            "пазл",
            "пазли",
            "розв'язати",
            "розвязати",
            "застряг",
            "що робити",
            "як пройти",
        ),
    ),
]


class ToolRouter:
    def __init__(self, knowledge_service, specs: list[ToolSpec] | None = None) -> None:
        self.knowledge_service = knowledge_service
        self.specs = specs or DEFAULT_TOOL_SPECS

    def select(self, *, game_id: str, query: str) -> ToolSelection | None:
        if self.knowledge_service is None:
            return None

        entity_registry = getattr(self.knowledge_service, "entity_registry", None)
        rewritten = rewrite_query(query, entity_registry=entity_registry)
        searchable_text = _merge_query_text(query, rewritten.retrieval_query)

        for spec in self.specs:
            if spec.game_id != game_id:
                continue
            if not _matches_intent(spec, searchable_text):
                continue

            if spec.intent == "list":
                return ToolSelection(
                    tool=spec.name,
                    arguments={"limit": spec.limit},
                )
            if spec.intent == "hint":
                return ToolSelection(
                    tool=spec.name,
                    arguments={"topic": _clean_hint_topic(searchable_text), "limit": spec.limit},
                )

            entities = self.knowledge_service.find_entities(
                game_id=game_id,
                text=searchable_text,
                content_type=spec.entity_content_type,
            )
            if len(entities) < spec.min_entities:
                continue

            return ToolSelection(
                tool=spec.name,
                arguments=_build_entity_arguments(spec=spec, entities=entities),
            )

        return None


def _matches_intent(spec: ToolSpec, text: str) -> bool:
    if spec.intent == "comparison":
        return _is_comparison_query(text)
    if spec.intent == "list":
        return _contains_trigger(text, spec.trigger_terms)
    if spec.intent == "hint":
        return _contains_trigger(text, spec.trigger_terms)
    return False


def _build_entity_arguments(*, spec: ToolSpec, entities: list[dict]) -> dict:
    if spec.intent == "comparison":
        prefix = spec.result_argument_name or "entity"
        return {
            f"{prefix}_a": entities[0]["canonical_name"],
            f"{prefix}_b": entities[1]["canonical_name"],
            "limit": spec.limit,
        }
    return {"limit": spec.limit}


def _contains_trigger(text: str, trigger_terms: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in trigger_terms)


def _merge_query_text(query: str, retrieval_query: str) -> str:
    if _normalize_query_for_compare(query) == _normalize_query_for_compare(retrieval_query):
        return query
    return f"{query} {retrieval_query}"


def _normalize_query_for_compare(text: str) -> str:
    return " ".join(re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE))


def _is_comparison_query(text: str) -> bool:
    tokens = set(re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE))
    comparison_terms = {
        "compare",
        "comparison",
        "versus",
        "vs",
        "difference",
        "stronger",
        "better",
        "порівняй",
        "порівняти",
        "порівняння",
        "порівня",
        "сильніше",
        "краще",
        "що",
    }
    return bool(tokens & comparison_terms)


def _clean_hint_topic(text: str) -> str:
    topic = re.sub(r"\s+", " ", text).strip()
    if len(topic) > 240:
        return topic[:240].rstrip()
    return topic
