from collections import Counter

from omnilibrarian.ingestion.sources.bg3_wiki import (
    BG3_WIKI_API_URL,
    BG3_WIKI_CATEGORY_BUDGETS,
    BG3_WIKI_DEFAULT_DISCOVERY_CATEGORIES,
    BG3_WIKI_DISCOVERY_CATEGORIES,
    build_bg3_wiki_seed_manifest,
    discover_bg3_wiki_category_manifest,
)


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeHTTPClient:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.calls = []

    def get(self, url: str, params: dict | None = None, headers: dict | None = None):
        self.calls.append({"url": url, "params": params, "headers": headers})
        return FakeResponse(self.payloads.pop(0))


def test_seed_manifest_has_balanced_category_budgets():
    manifest = build_bg3_wiki_seed_manifest()
    counts = Counter(ref.content_type for ref in manifest)

    assert len(manifest) <= 107
    assert counts["spell"] >= 25
    assert counts["item"] >= 20
    assert counts["class"] >= 12
    assert counts["mechanic"] >= 15
    assert counts["character"] >= 18
    assert counts["spell"] <= BG3_WIKI_CATEGORY_BUDGETS["spells"]
    assert counts["item"] <= BG3_WIKI_CATEGORY_BUDGETS["items"]
    assert counts["class"] <= BG3_WIKI_CATEGORY_BUDGETS["classes"]
    assert counts["mechanic"] <= BG3_WIKI_CATEGORY_BUDGETS["mechanics"]
    assert counts["character"] <= BG3_WIKI_CATEGORY_BUDGETS["companions"]


def test_seed_manifest_has_unique_doc_ids_and_bg3_wiki_urls():
    manifest = build_bg3_wiki_seed_manifest()
    doc_ids = [ref.doc_id for ref in manifest]

    assert len(doc_ids) == len(set(doc_ids))
    assert all(ref.doc_id.startswith("bg3_wiki:") for ref in manifest)
    assert all(ref.source_url.startswith("https://bg3.wiki/wiki/") for ref in manifest)


def test_seed_manifest_can_be_limited_by_category_and_total_count():
    manifest = build_bg3_wiki_seed_manifest(categories=["spells", "classes"], max_documents=10)
    counts = Counter(ref.content_type for ref in manifest)

    assert len(manifest) == 10
    assert set(counts) == {"spell", "class"}
    assert counts["spell"] > counts["class"]


def test_category_manifest_discovers_pages_from_mediawiki_category_api():
    client = FakeHTTPClient(
        [
            {
                "query": {
                    "categorymembers": [
                        {"title": "Fireball"},
                        {"title": "List of all spells"},
                        {"title": "Lightning Bolt"},
                    ]
                }
            }
        ]
    )

    manifest = discover_bg3_wiki_category_manifest(
        http_client=client,
        categories=["spells"],
        per_category_limit=10,
    )

    assert [ref.title for ref in manifest] == ["Fireball", "Lightning Bolt"]
    assert [ref.content_type for ref in manifest] == ["spell", "spell"]
    assert manifest[1].source_url == "https://bg3.wiki/wiki/Lightning_Bolt"
    assert client.calls[0]["url"] == BG3_WIKI_API_URL
    assert client.calls[0]["params"]["cmtitle"] == "Category:Spells"


def test_category_manifest_can_balance_discovered_categories_by_content_type():
    client = FakeHTTPClient(
        [
            {
                "query": {
                    "categorymembers": [
                        {"title": "Fireball"},
                        {"title": "Lightning Bolt"},
                    ]
                }
            },
            {
                "query": {
                    "categorymembers": [
                        {"title": "Astarion"},
                        {"title": "Shadowheart"},
                    ]
                }
            },
        ]
    )

    manifest = discover_bg3_wiki_category_manifest(
        http_client=client,
        categories=["spells", "characters"],
        per_category_limit=10,
        max_documents=3,
    )

    counts = Counter(ref.content_type for ref in manifest)
    assert len(manifest) == 3
    assert counts["spell"] == 2
    assert counts["character"] == 1


def test_default_category_discovery_profile_covers_main_page_knowledge_areas():
    expected_categories = {
        "abilities",
        "actions",
        "backgrounds",
        "classes",
        "companions",
        "conditions",
        "consumables",
        "creatures",
        "equipment",
        "feats",
        "items",
        "locations",
        "mechanics",
        "npcs",
        "origins",
        "quests",
        "races",
        "skills",
        "spells",
        "weapons",
    }

    assert expected_categories <= set(BG3_WIKI_DEFAULT_DISCOVERY_CATEGORIES)
    assert set(BG3_WIKI_DEFAULT_DISCOVERY_CATEGORIES) <= set(BG3_WIKI_DISCOVERY_CATEGORIES)
