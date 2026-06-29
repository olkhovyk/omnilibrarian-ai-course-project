import pytest

from omnilibrarian.ingestion.sources.blue_prince_reddit import (
    BLUE_PRINCE_REDDIT_CURATED_POST_URLS,
    build_blue_prince_reddit_manifest,
)
from omnilibrarian.ingestion.sources.blue_prince_wiki import build_blue_prince_wiki_seed_manifest


def test_build_blue_prince_wiki_seed_manifest_uses_wiki_gg_urls():
    manifest = build_blue_prince_wiki_seed_manifest(categories=["rooms"], max_documents=3)

    assert [ref.title for ref in manifest] == ["Rooms", "Category:Rooms", "Parlor"]
    assert manifest[0].doc_id == "blue_prince_wiki:Rooms"
    assert manifest[0].source_url == "https://blueprince.wiki.gg/wiki/Rooms"
    assert manifest[1].source_url == "https://blueprince.wiki.gg/wiki/Category:Rooms"
    assert all(ref.content_type == "rooms" for ref in manifest)


def test_build_blue_prince_wiki_seed_manifest_rejects_unknown_category():
    with pytest.raises(ValueError, match="Unknown Blue Prince wiki category"):
        build_blue_prince_wiki_seed_manifest(categories=["spells"])


def test_build_blue_prince_reddit_manifest_keeps_permalinks_as_community_source():
    manifest = build_blue_prince_reddit_manifest(
        ["https://www.reddit.com/r/BluePrince/comments/abc123/example_hint_thread/"]
    )

    assert manifest[0].doc_id == "blue_prince_reddit:abc123_example_hint_thread"
    assert manifest[0].source_url == "https://www.reddit.com/r/BluePrince/comments/abc123/example_hint_thread/"
    assert manifest[0].title == "abc123 example hint thread"
    assert manifest[0].content_type == "community_tip"


def test_build_blue_prince_reddit_manifest_has_curated_default_posts():
    manifest = build_blue_prince_reddit_manifest()

    assert len(manifest) == len(BLUE_PRINCE_REDDIT_CURATED_POST_URLS)
    assert manifest[0].doc_id.startswith("blue_prince_reddit:1n0wdv6")
    assert manifest[0].content_type == "community_tip"
    assert manifest[1].content_type == "patch_note"


def test_build_blue_prince_reddit_manifest_rejects_other_subreddits():
    with pytest.raises(ValueError, match="not from r/BluePrince"):
        build_blue_prince_reddit_manifest(["https://www.reddit.com/r/OtherGame/comments/abc123/post/"])
