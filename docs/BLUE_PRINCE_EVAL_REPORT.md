# Blue Prince Eval Report

Date: 2026-06-12

This report captures the first complete Blue Prince evaluation loop for
OmniLibrarian. It demonstrates that the same ingestion, RAG, eval, and MCP
routing architecture used for BG3 can support a second game tenant.

## Corpus

Source:

- `blue_prince_wiki`: `https://blueprince.wiki.gg/`
- `blue_prince_reddit`: curated posts from `https://www.reddit.com/r/BluePrince/`

Pipeline:

```powershell
python scripts/run_blue_prince_pipeline.py
```

The pipeline fetches wiki pages and curated Reddit posts, writes raw cached
documents, normalizes and chunks them, builds an entity registry from wiki facts,
indexes each source slice into Qdrant under `game_id=blue_prince`, and runs
retrieval plus tool-routing evals.

The wiki remains the primary factual source. Reddit is used as a community/hint
source through source-aware retrieval policy.

## Retrieval Eval

Command:

```powershell
python scripts/omni.py eval blue_prince retrieval
```

Current result:

| Metric | Value |
| --- | ---: |
| Total cases | 12 |
| Hit@1 | 0.917 |
| Hit@3 | 1.000 |
| Hit@5 | 1.000 |
| MRR | 0.958 |
| Coverage@5 | 1.000 |
| Term coverage@5 | 1.000 |
| Tenant isolation | 1.000 |
| Source hit@5 | Run locally after Reddit indexing |
| Avg latency | 84.667 ms |
| P95 latency | 86.000 ms |

Category summary:

| Category | Cases | Hit@1 | Hit@5 |
| --- | ---: | ---: | ---: |
| Items | 1 | 1.000 | 1.000 |
| Lore | 2 | 1.000 | 1.000 |
| Mechanics | 2 | 1.000 | 1.000 |
| Puzzles | 2 | 1.000 | 1.000 |
| Rooms | 5 | 0.800 | 1.000 |

The only missed Hit@1 case is `bp_rooms_overview`: the top result is the general
`Blue Prince` page, while the expected `Rooms` page is ranked second. This is
acceptable for the current demo because Hit@3 and Hit@5 are perfect, but it is
a useful future reranking case.

The current golden set also includes community hint cases that expect
`blue_prince_reddit` in top-5. These are tracked separately through
`source_hit_at_5`, so Reddit usefulness can be measured without pretending
community threads are the canonical factual source.

## Tool-Routing Eval

Command:

```powershell
python scripts/eval_tool_routing.py --golden data/evals/blue_prince_tool_routing_golden.jsonl --entities-path data/processed/blue_prince/blue_prince_wiki_entities.json --output data/evals/blue_prince_tool_routing_results.json
```

Current result:

| Metric | Value |
| --- | ---: |
| Total cases | 5 |
| Accuracy | 1.000 |
| Avg latency | 5.400 ms |
| Direct RAG accuracy | 1.000 |
| Hint tool accuracy | 1.000 |

The router correctly sends puzzle/hint-style questions to
`search_puzzle_hint`, while ordinary factual questions remain in direct RAG.

## Answer Eval

Answer-level eval is available and should be run after retrieval quality is stable:

```powershell
python scripts/omni.py eval blue_prince answers
```

Unlike retrieval eval, this calls the real LLM once per case. The resulting JSON
report checks whether the answer has sources, inline citations, expected source
titles, expected answer terms, and no unexpected insufficient-context response.

## Quality Iteration

Initial Blue Prince retrieval was much weaker:

| Metric | Initial | Current |
| --- | ---: | ---: |
| Hit@1 | 0.300 | 0.917 |
| Hit@5 | 0.600 | 1.000 |
| MRR | 0.450 | 0.958 |
| Term coverage@5 | 0.700 | 1.000 |
| Tenant isolation | 1.000 | 1.000 |

Main fixes:

- Reduced over-aggressive fuzzy entity rewriting. Generic words such as `room`,
  `work`, `blue`, and `prince` no longer rewrite to page titles like
  `Ballroom`, `Network`, or `Blue Prince`.
- Excluded service pages such as `Blue Prince Wiki/contribute` from wiki page
  discovery.
- Replaced invalid golden targets such as `Puzzles`, `Lore`, and `Walkthrough`
  with real corpus pages like `Family Core Puzzle`, `Castling Puzzle`,
  `The History of Orindia`, `Blue Tents`, and `Drafting`.
- Added curated Reddit ingestion as a separate source slice.
- Added source-aware retrieval policy: wiki is preferred for factual questions,
  while Reddit can be promoted for hint/community wording.
- Added trace fields for `source_mix`, per-chunk `source_id`, retrieval source,
  and source policy reasons.
- Added answer-level eval for citations, expected source titles, answer terms,
  and unexpected insufficient-context responses.

## Course Defense Takeaway

This eval proves that OmniLibrarian is not hardcoded to BG3. Blue Prince uses
the same platform boundaries:

- source-specific wiki fetcher and normalizer;
- shared raw cache and chunking pipeline;
- shared entity registry;
- shared Qdrant collection filtered by `game_id`;
- shared hybrid retrieval and reranking;
- source policy for wiki authority vs Reddit community hints;
- game-specific MCP server and declarative tool routing;
- shared eval runners.

The project can now show a credible multi-tenant AI architecture: one platform,
multiple games, isolated retrieval, measured quality, and game-specific tools.

## Follow-Ups

- Improve the `bp_rooms_overview` ranking so `Rooms` beats the general
  `Blue Prince` page for overview questions.
- Clean duplicate rewritten topic text for Ukrainian Blue Prince hint routing.
- Run local retrieval eval after Reddit indexing and update this report with the
  actual `source_hit_at_5` value.
