from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
import re
from pathlib import Path
from urllib.parse import quote

import httpx

from omnilibrarian.ingestion.cache import IngestionCache, compute_content_hash
from omnilibrarian.ingestion.documents import RawDocument, read_raw_document, write_raw_document
from omnilibrarian.ingestion.sources.base import SourceRef


BG3_WIKI_SOURCE_ID = "bg3_wiki"
BG3_WIKI_API_URL = "https://bg3.wiki/w/api.php"
BG3_WIKI_LICENSE = "CC BY-NC-SA 4.0 or CC BY-SA 4.0 where applicable"
BG3_WIKI_CATEGORY_BUDGETS = {
    "spells": 30,
    "items": 25,
    "classes": 14,
    "mechanics": 20,
    "companions": 18,
}

BG3_WIKI_DISCOVERY_CATEGORIES = {
    "abilities": "Category:Abilities",
    "actions": "Category:Actions",
    "alchemy": "Category:Alchemy",
    "backgrounds": "Category:Backgrounds",
    "bonus_actions": "Category:Bonus actions",
    "classes": "Category:Classes",
    "companions": "Category:Companions",
    "conditions": "Category:Conditions",
    "consumables": "Category:Consumables",
    "creatures": "Category:Creatures",
    "damage_types": "Category:Damage Types",
    "dice_rolls": "Category:Dice rolls",
    "spells": "Category:Spells",
    "equipment": "Category:Equipment",
    "feats": "Category:Feats",
    "illithid_powers": "Category:Illithid powers",
    "inspiration": "Category:Inspiration",
    "items": "Category:Items",
    "locations": "Category:Locations",
    "mechanics": "Category:Gameplay mechanics",
    "npcs": "Category:Non-player characters",
    "origins": "Category:Origins",
    "permanent_bonuses": "Category:Permanent bonuses",
    "proficiency": "Category:Proficiency",
    "quests": "Category:Quests",
    "races": "Category:Races",
    "reactions": "Category:Reactions",
    "resources": "Category:Resources",
    "resting": "Category:Resting",
    "skills": "Category:Skills",
    "spellcasting": "Category:Spellcasting",
    "weapon_actions": "Category:Weapon actions",
    "weapons": "Category:Weapons",
    "characters": "Category:Characters",
}

BG3_WIKI_DEFAULT_DISCOVERY_CATEGORIES = [
    "spells",
    "classes",
    "races",
    "origins",
    "backgrounds",
    "feats",
    "abilities",
    "skills",
    "characters",
    "companions",
    "npcs",
    "creatures",
    "quests",
    "locations",
    "items",
    "equipment",
    "weapons",
    "consumables",
    "mechanics",
    "resources",
    "actions",
    "bonus_actions",
    "reactions",
    "weapon_actions",
    "illithid_powers",
    "spellcasting",
    "resting",
    "conditions",
    "alchemy",
    "damage_types",
    "permanent_bonuses",
    "proficiency",
    "inspiration",
    "dice_rolls",
]

BG3_WIKI_SEED_PAGES = {
    "spells": [
        "Fireball",
        "Magic_Missile",
        "Eldritch_Blast",
        "Haste",
        "Misty_Step",
        "Counterspell",
        "Shield",
        "Guiding_Bolt",
        "Healing_Word",
        "Cure_Wounds",
        "Bless",
        "Bane",
        "Command",
        "Hold_Person",
        "Hypnotic_Pattern",
        "Spirit_Guardians",
        "Scorching_Ray",
        "Chromatic_Orb",
        "Thunderwave",
        "Cloud_of_Daggers",
        "Darkness",
        "Invisibility",
        "Greater_Invisibility",
        "Fly",
        "Lightning_Bolt",
        "Ice_Storm",
        "Wall_of_Fire",
        "Disintegrate",
        "Globe_of_Invulnerability",
        "Otto%27s_Irresistible_Dance",
    ],
    "items": [
        "Phalar_Aluve",
        "Blood_of_Lathander",
        "Markoheshkir",
        "Mourning_Frost",
        "Staff_of_Spellpower",
        "The_Spellsparkler",
        "Potent_Robe",
        "Robe_of_the_Weave",
        "Birthright",
        "Warped_Headband_of_Intellect",
        "Gloves_of_Dexterity",
        "Gloves_of_Belligerent_Skies",
        "Caustic_Band",
        "Callous_Glow_Ring",
        "Risky_Ring",
        "Ring_of_Protection",
        "Amulet_of_Greater_Health",
        "Pearl_of_Power_Amulet",
        "Boots_of_Speed",
        "Disintegrating_Night_Walkers",
        "Potion_of_Speed",
        "Elixir_of_Bloodlust",
        "Elixir_of_Hill_Giant_Strength",
        "Scroll_of_Fireball",
        "Scroll_of_Haste",
    ],
    "classes": [
        "Barbarian",
        "Bard",
        "Cleric",
        "Druid",
        "Fighter",
        "Monk",
        "Paladin",
        "Ranger",
        "Rogue",
        "Sorcerer",
        "Warlock",
        "Wizard",
        "Multiclassing",
        "Subclasses",
    ],
    "mechanics": [
        "Dice_rolls",
        "Advantage",
        "Disadvantage",
        "Armour_Class",
        "Initiative",
        "Concentration",
        "Conditions",
        "Damage_Types",
        "Saving_throws",
        "Ability_scores",
        "Proficiency",
        "Actions",
        "Bonus_action",
        "Reaction",
        "Movement",
        "Resting",
        "Spellcasting",
        "Ritual_spells",
        "Opportunity_Attack",
        "Difficulty",
    ],
    "companions": [
        "Astarion",
        "Shadowheart",
        "Gale",
        "Lae%27zel",
        "Wyll",
        "Karlach",
        "Halsin",
        "Minthara",
        "Jaheira",
        "Minsc",
        "Scratch",
        "Owlbear_Cub",
        "Us",
        "Shovel_(familiar)",
        "Tara",
        "Camp_followers",
        "Hirelings",
        "Companions",
    ],
}

BG3_WIKI_CONTENT_TYPES = {
    "abilities": "ability",
    "actions": "action",
    "alchemy": "mechanic",
    "backgrounds": "background",
    "bonus_actions": "action",
    "spells": "spell",
    "items": "item",
    "classes": "class",
    "companions": "character",
    "conditions": "condition",
    "consumables": "item",
    "creatures": "creature",
    "damage_types": "mechanic",
    "dice_rolls": "mechanic",
    "equipment": "item",
    "feats": "feat",
    "illithid_powers": "mechanic",
    "inspiration": "mechanic",
    "locations": "location",
    "mechanics": "mechanic",
    "npcs": "character",
    "origins": "origin",
    "permanent_bonuses": "mechanic",
    "proficiency": "mechanic",
    "quests": "quest",
    "races": "race",
    "reactions": "action",
    "resources": "mechanic",
    "resting": "mechanic",
    "skills": "skill",
    "spellcasting": "mechanic",
    "weapon_actions": "action",
    "weapons": "item",
    "characters": "character",
}


@dataclass(frozen=True)
class FetchResult:
    status: str
    raw_document: RawDocument
    raw_path: Path


class BG3WikiFetcher:
    def __init__(
        self,
        *,
        cache: IngestionCache,
        raw_root: str | Path,
        http_client: httpx.Client | None = None,
        now=None,
    ) -> None:
        self.cache = cache
        self.raw_root = Path(raw_root)
        self.http_client = http_client or httpx.Client(
            timeout=20.0,
            headers={"user-agent": "OmniLibrarianCourseProject/0.1"},
            follow_redirects=True,
        )
        self._now = now or (lambda: datetime.now(UTC))

    def fetch(self, ref: SourceRef, *, ttl_hours: int = 168, force_refresh: bool = False) -> FetchResult:
        now = self._now()
        entry = self.cache.get(ref.doc_id)
        if entry and not force_refresh and self.cache.is_fresh(entry, now=now, ttl_hours=ttl_hours):
            raw_path = Path(entry.raw_path)
            return FetchResult(status="cached", raw_document=read_raw_document(raw_path), raw_path=raw_path)

        headers = {} if force_refresh else self._conditional_headers(entry)
        response = self.http_client.get(ref.source_url, headers=headers)
        raw_path = self._raw_path(ref)

        if response.status_code == 304 and entry is not None:
            self.cache.mark_not_modified(ref.doc_id, checked_at=now)
            existing_path = Path(entry.raw_path)
            return FetchResult(
                status="not_modified",
                raw_document=read_raw_document(existing_path),
                raw_path=existing_path,
            )

        response.raise_for_status()
        text_en = extract_bg3_wiki_text(response.text)
        raw_document = RawDocument(
            doc_id=ref.doc_id,
            game_id="bg3",
            source_id=BG3_WIKI_SOURCE_ID,
            source_url=ref.source_url,
            title=ref.title,
            text_en=text_en,
            content_type=ref.content_type,
            fetched_at=now.isoformat(),
            license=BG3_WIKI_LICENSE,
        )
        content_hash = compute_content_hash(raw_document.text_en)
        status = "unchanged" if entry and entry.content_hash == content_hash else "fetched"

        write_raw_document(raw_path, raw_document)
        self.cache.upsert_fetched(
            doc_id=raw_document.doc_id,
            game_id=raw_document.game_id,
            source_id=raw_document.source_id,
            source_url=raw_document.source_url,
            raw_path=str(raw_path),
            content_hash=content_hash,
            fetched_at=now,
            checked_at=now,
            status_code=response.status_code,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
        return FetchResult(status=status, raw_document=raw_document, raw_path=raw_path)

    def fetch_manifest(self) -> list[SourceRef]:
        return initial_bg3_wiki_manifest()

    def discover_manifest(
        self,
        *,
        categories: list[str] | None = None,
        per_category_limit: int = 100,
        max_documents: int | None = None,
    ) -> list[SourceRef]:
        return discover_bg3_wiki_category_manifest(
            http_client=self.http_client,
            categories=categories,
            per_category_limit=per_category_limit,
            max_documents=max_documents,
        )

    def _raw_path(self, ref: SourceRef) -> Path:
        safe_doc_id = ref.doc_id.replace(":", "_").replace("/", "_")
        return self.raw_root / "bg3" / BG3_WIKI_SOURCE_ID / f"{safe_doc_id}.json"

    def _conditional_headers(self, entry) -> dict[str, str]:
        if entry is None:
            return {}

        headers: dict[str, str] = {}
        if entry.etag:
            headers["if-none-match"] = entry.etag
        if entry.last_modified:
            headers["if-modified-since"] = entry.last_modified
        return headers


class _MainContentTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capture_depth = 0
        self._skip_depth = 0
        self._pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        element_id = attrs_dict.get("id", "")
        class_name = attrs_dict.get("class", "")

        if element_id == "mw-content-text":
            self._capture_depth = 1
            return

        if self._capture_depth:
            self._capture_depth += 1
            if tag in {"script", "style", "table", "sup"} or "mw-editsection" in class_name:
                self._skip_depth += 1
            if tag in {"p", "li", "h2", "h3", "h4", "br"}:
                self._pieces.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if not self._capture_depth:
            return
        if self._skip_depth:
            self._skip_depth -= 1
        self._capture_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._capture_depth and not self._skip_depth:
            text = data.strip()
            if text:
                self._pieces.append(f"{text} ")

    def text(self) -> str:
        raw = "".join(self._pieces)
        lines = []
        for line in raw.splitlines():
            clean_line = re.sub(r"\s+", " ", line).strip()
            if clean_line:
                lines.append(clean_line)
        return "\n".join(lines).strip()


def extract_bg3_wiki_text(html: str) -> str:
    parser = _MainContentTextParser()
    parser.feed(html)
    text = parser.text()
    if not text:
        raise ValueError("Could not extract article text from BG3 wiki HTML.")
    return text


def initial_bg3_wiki_manifest() -> list[SourceRef]:
    return build_bg3_wiki_seed_manifest()


def build_bg3_wiki_seed_manifest(
    *,
    categories: list[str] | None = None,
    max_documents: int | None = None,
) -> list[SourceRef]:
    selected_categories = categories or list(BG3_WIKI_SEED_PAGES)
    refs: list[SourceRef] = []

    for category in selected_categories:
        pages = BG3_WIKI_SEED_PAGES[category][: BG3_WIKI_CATEGORY_BUDGETS[category]]
        for page in pages:
            refs.append(_source_ref(category, page))

    refs = _dedupe_refs(refs)
    if max_documents is None or len(refs) <= max_documents:
        return refs
    return _take_balanced(refs, selected_categories, max_documents)


def _source_ref(category: str, page: str) -> SourceRef:
    title = page.replace("_", " ")
    title = title.replace("%27", "'")
    return SourceRef(
        doc_id=f"{BG3_WIKI_SOURCE_ID}:{page}",
        source_url=f"https://bg3.wiki/wiki/{page}",
        title=title,
        content_type=BG3_WIKI_CONTENT_TYPES[category],
    )


def _dedupe_refs(refs: list[SourceRef]) -> list[SourceRef]:
    seen: set[str] = set()
    deduped: list[SourceRef] = []
    for ref in refs:
        if ref.doc_id in seen:
            continue
        seen.add(ref.doc_id)
        deduped.append(ref)
    return deduped


def _take_balanced(refs: list[SourceRef], categories: list[str], max_documents: int) -> list[SourceRef]:
    by_type = {BG3_WIKI_CONTENT_TYPES[category]: [] for category in categories}
    for ref in refs:
        if ref.content_type in by_type:
            by_type[ref.content_type].append(ref)

    total_budget = sum(BG3_WIKI_CATEGORY_BUDGETS[category] for category in categories)
    allocations: dict[str, int] = {}
    fractions: list[tuple[float, str]] = []
    assigned = 0
    for category in categories:
        exact = max_documents * BG3_WIKI_CATEGORY_BUDGETS[category] / total_budget
        base = max(1, int(exact))
        content_type = BG3_WIKI_CONTENT_TYPES[category]
        allocations[content_type] = min(base, len(by_type[content_type]))
        assigned += allocations[content_type]
        fractions.append((exact - int(exact), content_type))

    for _, content_type in sorted(fractions, reverse=True):
        if assigned >= max_documents:
            break
        if allocations[content_type] < len(by_type[content_type]):
            allocations[content_type] += 1
            assigned += 1

    selected: list[SourceRef] = []
    for category in categories:
        content_type = BG3_WIKI_CONTENT_TYPES[category]
        selected.extend(by_type[content_type][: allocations[content_type]])

    selected = selected[:max_documents]
    if len(selected) == max_documents:
        return selected

    existing = {ref.doc_id for ref in selected}
    for ref in refs:
        if ref.doc_id in existing:
            continue
        selected.append(ref)
        if len(selected) == max_documents:
            return selected
    return selected


def discover_bg3_wiki_category_manifest(
    *,
    http_client: httpx.Client,
    categories: list[str] | None = None,
    per_category_limit: int = 100,
    max_documents: int | None = None,
) -> list[SourceRef]:
    selected_categories = categories or BG3_WIKI_DEFAULT_DISCOVERY_CATEGORIES
    refs: list[SourceRef] = []
    for category in selected_categories:
        refs.extend(_discover_category_refs(http_client=http_client, category=category, limit=per_category_limit))

    refs = _dedupe_refs(refs)
    if max_documents is None or len(refs) <= max_documents:
        return refs
    return _take_evenly_by_content_type(refs, max_documents=max_documents)


def _discover_category_refs(*, http_client: httpx.Client, category: str, limit: int) -> list[SourceRef]:
    if category not in BG3_WIKI_DISCOVERY_CATEGORIES:
        raise ValueError(f"BG3 wiki category discovery is not configured for category={category!r}")

    refs: list[SourceRef] = []
    cmcontinue = None
    while len(refs) < limit:
        remaining = limit - len(refs)
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": BG3_WIKI_DISCOVERY_CATEGORIES[category],
            "cmnamespace": "0",
            "cmtype": "page",
            "cmlimit": str(min(500, remaining)),
            "format": "json",
            "formatversion": "2",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        response = http_client.get(BG3_WIKI_API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
        members = payload.get("query", {}).get("categorymembers", [])
        if not members:
            break

        for member in members:
            title = member.get("title")
            if not title or _should_skip_discovered_title(title):
                continue
            refs.append(_source_ref_from_title(category=category, title=title))
            if len(refs) >= limit:
                break

        cmcontinue = payload.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break

    return _dedupe_refs(refs)


def _source_ref_from_title(*, category: str, title: str) -> SourceRef:
    page = title.replace(" ", "_")
    return SourceRef(
        doc_id=f"{BG3_WIKI_SOURCE_ID}:{page}",
        source_url=f"https://bg3.wiki/wiki/{quote(page, safe='')}",
        title=title,
        content_type=BG3_WIKI_CONTENT_TYPES[category],
    )


def _should_skip_discovered_title(title: str) -> bool:
    lowered = title.casefold()
    return lowered.startswith(("category:", "file:", "template:", "list of"))


def _take_evenly_by_content_type(refs: list[SourceRef], *, max_documents: int) -> list[SourceRef]:
    by_type: dict[str, list[SourceRef]] = {}
    content_type_order: list[str] = []
    for ref in refs:
        if ref.content_type not in by_type:
            content_type_order.append(ref.content_type)
        by_type.setdefault(ref.content_type, []).append(ref)

    selected: list[SourceRef] = []
    while len(selected) < max_documents:
        added = False
        for content_type in content_type_order:
            bucket = by_type[content_type]
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            added = True
            if len(selected) >= max_documents:
                break
        if not added:
            break
    return selected
