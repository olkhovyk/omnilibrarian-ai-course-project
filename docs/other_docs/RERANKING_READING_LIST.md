# Reranking Reading List

This note collects theory and practical references for the next RAG step:
moving from pure vector search to reranking and hybrid retrieval.

## Why this matters for OmniLibrarian

The current BG3 retrieval uses dense vector search. It already finds relevant
chunks, but queries such as `Fireball damage` can still return nearby spell or
mechanic pages after the best Fireball results.

The next retrieval architecture should look like this:

```text
Query
  -> first-stage retrieval: get top 20-50 candidates
  -> reranking / hybrid scoring
  -> final top 5 chunks for the LLM
```

The goal is to improve precision while keeping retrieval fast.

## Recommended reading order

### 1. Pinecone: Rerankers and Two-Stage Retrieval

Best starting point for intuition.

Focus on:
- recall vs precision
- why vector search is usually a first-stage retriever
- why rerankers run only on a small candidate set

Link: https://www.pinecone.io/learn/series/rag/rerankers/

### 2. Sentence Transformers: Retrieve & Re-Rank

Relevant to our Python stack.

Focus on:
- bi-encoder vs cross-encoder
- fast embedding search vs slower pairwise relevance scoring
- using a cross-encoder to reorder retrieved chunks

Links:
- https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/
- https://github.com/huggingface/sentence-transformers/blob/main/docs/cross_encoder/usage/usage.rst

### 3. Qdrant: Hybrid Search with Reranking

Relevant because our vector DB is Qdrant.

Focus on:
- dense retrieval
- sparse retrieval
- reranking as a separate retrieval stage
- production-style RAG retrieval flow

Link: https://qdrant.tech/documentation/tutorials-basics/reranking-hybrid-search/

### 4. Qdrant: Hybrid Queries / RRF

Useful for combining multiple retrieval signals.

Focus on:
- dense + sparse search
- reciprocal rank fusion
- why rank fusion can be easier than merging raw scores

Link: https://qdrant.tech/documentation/search/hybrid-queries/

### 5. BAAI/bge-m3 model card

Relevant because we already use `BAAI/bge-m3` for local embeddings.

Focus on:
- dense retrieval
- sparse retrieval
- multi-vector retrieval
- why this model can support more advanced retrieval without changing the
  whole embedding stack

Link: https://huggingface.co/BAAI/bge-m3

### 6. Reciprocal Rank Fusion paper

Optional but useful if you want to understand RRF more formally.

Focus on:
- combining rankings instead of raw scores
- why RRF is robust for multiple retrieval systems

Link: https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf

## Mental model

```text
First-stage retrieval:
  "Give me 20-50 candidates where the correct answer is likely present."

Reranking:
  "Now carefully score query + chunk pairs and reorder them."

Hybrid search:
  "Search both by meaning and exact words."

RRF:
  "Merge multiple ranked lists without depending on incompatible score scales."
```

## Likely implementation path later

For this project, the most practical next step is not a heavy reranker first.
Start with a simple metadata-aware reranking layer:

1. Retrieve top 20 from Qdrant.
2. Boost chunks whose title appears in the query.
3. Boost exact keyword matches in chunk text.
4. Optionally prefer matching content types.
5. Return the final top 5.

After that, consider a cross-encoder reranker if quality still needs a visible
improvement.
