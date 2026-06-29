# Course Project Proposal: OmniLibrarian

## Назва

**OmniLibrarian: Multi-tenant AI Gateway з RAG, LangGraph та MCP для ігрових knowledge bases**

## Ідея проєкту

OmniLibrarian - це multi-tenant RAG + agent platform для відеоігор. Система виступає як розумний асистент, який може відповідати на питання по кількох іграх одночасно, але з чіткою ізоляцією даних і tools для кожного домену.

На старті плануються два tenants:

- `bg3` - Baldur's Gate 3
- `blue_prince` - Blue Prince

Користувач може ставити питання українською, навіть якщо база знань зібрана англійською. Система робить cross-lingual semantic search, дістає релевантний контекст, за потреби викликає game-specific MCP tools і повертає відповідь українською.

## Основна цінність

Це не просто "чат з документами", а платформа:

- кожна гра ізольована як tenant;
- кожна гра може мати власний MCP server;
- gateway не прив'язаний до конкретної гри;
- нову гру можна додати без переписування основної логіки;
- LangGraph дає контрольований agent workflow;
- LangSmith або Phoenix дають observability та eval.

## MVP scope

У MVP варто залишити тільки те, що демонструє головну архітектуру.

Обов'язково:

1. **2 гри / 2 tenants**
   - Baldur's Gate 3
   - Blue Prince

2. **FastAPI Gateway**
   - endpoint `/chat`
   - приймає `message`, `session_id`, опціонально `game_id`
   - повертає відповідь, sources, tool calls, latency

3. **Qdrant multi-tenancy**
   - одна collection
   - payload filter по `game_id`
   - tenant isolation tests

4. **Cross-lingual RAG**
   - документи англійською
   - запити українською
   - відповідь українською
   - multilingual embeddings, наприклад `BAAI/bge-m3` або `intfloat/multilingual-e5`

5. **LangGraph agent workflow**
   - routing
   - retrieval
   - MCP tool selection
   - tool call
   - answer generation
   - optional grounding check

6. **MCP server per game**
   - `mcp_bg3_server`
   - `mcp_blue_prince_server`

7. **Eval**
   - router accuracy
   - retrieval recall@k
   - answer groundedness
   - tenant isolation
   - latency

8. **Demo UI**
   - Streamlit або Next.js
   - вибір гри
   - chat
   - sources
   - tool calls
   - trace/debug panel

## Що не варто робити у MVP

Ці речі краще залишити як stretch goals:

- кастомний PyTorch router;
- dynamic MCP discovery;
- складний reranker;
- auth / billing / real user accounts;
- Kubernetes;
- fine-tuning;
- складна довгострокова memory.

Причина: сам по собі RAG + LangGraph + MCP + multi-tenancy вже достатньо великий scope для курсової. PyTorch router може перетворити роботу в окремий ML-проєкт і забрати фокус.

## Архітектура

```text
User
  |
  v
FastAPI Gateway
  |
  v
LangGraph Workflow
  |
  +--> detect_game_and_intent
  |
  +--> retrieve_context
  |       |
  |       v
  |     Qdrant
  |     filter: game_id
  |
  +--> select_mcp_tool
  |
  +--> call_game_mcp_server
  |       |
  |       +--> BG3 MCP Server
  |       |
  |       +--> Blue Prince MCP Server
  |
  +--> generate_answer_uk
  |
  +--> verify_grounding
  |
  v
Response with answer, sources, tool calls, metrics
```

## LangGraph workflow

Рекомендований graph:

```text
START
  -> route_request
  -> retrieve_context
  -> decide_tool
  -> call_tool_or_skip
  -> generate_answer
  -> verify_answer
  -> END
```

State може містити:

```python
class AgentState(TypedDict):
    message: str
    session_id: str
    game_id: str | None
    detected_game_id: str
    intent: str
    query_embedding: list[float]
    retrieved_chunks: list[dict]
    selected_tool: str | None
    tool_result: dict | None
    answer: str
    sources: list[dict]
    trace: list[dict]
```

## MCP servers

### BG3 MCP Server

Приклади tools:

```text
get_spell_info(spell_name)
get_item_info(item_name)
get_class_info(class_name)
roll_dice(dice_formula)
```

Приклади питань:

```text
Яка шкода від Fireball?
Які предмети корисні для wizard?
Кинь d20 для перевірки persuasion.
```

### Blue Prince MCP Server

Приклади tools:

```text
get_room_info(room_name)
get_item_info(item_name)
search_puzzle_hint(topic)
```

Приклади питань:

```text
Що робить Laboratory?
Де може знадобитися keycard?
Дай підказку по puzzle без спойлерів.
```

## Multi-tenancy

Для MVP найкраще використати одну Qdrant collection з payload filter:

```json
{
  "game_id": "bg3",
  "source": "wiki",
  "doc_type": "spell",
  "title": "Fireball"
}
```

Пошук завжди має містити filter:

```text
game_id == detected_game_id
```

Це дозволяє показати tenant isolation:

- запит по BG3 не повертає chunks з Blue Prince;
- запит по Blue Prince не повертає chunks з BG3.

## Cross-lingual retrieval

Ключова фіча: користувач пише українською, а документи залишаються англійською.

Приклад:

```text
User: Яка шкода від вогняної кулі?
Retrieved doc: Fireball is a level 3 evocation spell...
Answer: Fireball у BG3 завдає 8d6 fire damage...
```

Для цього потрібна multilingual embedding model:

- `BAAI/bge-m3`
- `intfloat/multilingual-e5-base`
- `intfloat/multilingual-e5-large`

## Routing

У MVP:

- rule-based router або LLM router;
- визначає `game_id` і `intent`.

Приклад output:

```json
{
  "game_id": "bg3",
  "intent": "spell_info"
}
```

Stretch goal:

- легкий PyTorch classifier для intent/game routing.

Але я б не робив PyTorch router у першій версії. Його краще додати після того, як RAG + MCP + LangGraph вже стабільно працюють.

## Eval plan

Потрібен golden set мінімум на 30-50 питань.

Групи тестів:

1. **Game routing accuracy**
   - чи правильно визначено гру.

2. **Intent accuracy**
   - spell info, item info, room info, puzzle hint, dice roll.

3. **Retrieval quality**
   - recall@5
   - чи знайдено правильний документ.

4. **Tenant isolation**
   - BG3 queries не мають повертати Blue Prince chunks.

5. **Groundedness**
   - відповідь базується на retrieved context/tool result.

6. **Latency**
   - p50 / p95.

7. **Tool accuracy**
   - чи правильний MCP tool був викликаний.

## Observability

Потрібно підключити LangSmith або Arize Phoenix.

У traces має бути видно:

```text
route_request
retrieve_context
qdrant_search
select_tool
mcp_tool_call
generate_answer
verify_grounding
```

Це дасть гарний матеріал для захисту: можна показати не тільки фінальну відповідь, а весь шлях прийняття рішення.

## Tech stack

Recommended stack:

- Python
- FastAPI
- LangGraph
- MCP SDK
- Qdrant
- Sentence Transformers
- OpenRouter / OpenAI / Anthropic
- LangSmith або Phoenix
- Docker Compose
- Streamlit або Next.js
- pytest

## Milestones

### Milestone 1: Data ingestion

- зібрати невеликий dataset для BG3;
- зібрати невеликий dataset для Blue Prince;
- нормалізувати documents;
- додати metadata `game_id`, `source`, `title`, `doc_type`;
- завантажити chunks у Qdrant.

### Milestone 2: Basic RAG

- FastAPI `/chat`;
- multilingual embeddings;
- Qdrant search з `game_id` filter;
- відповідь українською;
- sources у response.

### Milestone 3: LangGraph workflow

- route node;
- retrieve node;
- answer node;
- state object;
- trace/debug output.

### Milestone 4: MCP tools

- BG3 MCP server;
- Blue Prince MCP server;
- tool selection node;
- tool call node;
- tool results у фінальній відповіді.

### Milestone 5: Eval

- golden set 30-50 питань;
- local eval;
- LangSmith/Phoenix experiment;
- metrics report.

### Milestone 6: UI and demo

- chat UI;
- game selector;
- sources panel;
- tool calls panel;
- traces panel;
- demo сценарії для захисту.

## Demo scenarios

### Scenario 1: Cross-lingual BG3 RAG

```text
User: Яка шкода від Fireball у BG3?
```

Expected:

- game detected: `bg3`
- intent: `spell_info`
- retrieved English Fireball docs
- optional MCP tool `get_spell_info`
- Ukrainian grounded answer

### Scenario 2: Tenant isolation

```text
User: Що робить Laboratory?
```

Expected:

- game detected: `blue_prince`
- search only over `game_id=blue_prince`
- no BG3 chunks in sources

### Scenario 3: MCP tool call

```text
User: Кинь d20 для persuasion check.
```

Expected:

- game detected: `bg3`
- intent: `dice_roll`
- MCP tool: `roll_dice("1d20")`
- answer includes roll result

### Scenario 4: Follow-up question

```text
User: Яка шкода від Fireball?
Assistant: ...
User: А які предмети підсилюють fire spells?
```

Expected:

- session context remembers BG3/fire magic topic
- retrieval focuses on relevant BG3 items
- answer in Ukrainian

## Ризики

1. **Занадто широкий scope**
   - Рішення: не робити PyTorch router у MVP.

2. **Якість даних**
   - Рішення: взяти маленький, але чистий dataset.

3. **MCP complexity**
   - Рішення: почати з 2-3 простих tools на гру.

4. **Cross-lingual retrieval може бути слабким**
   - Рішення: протестувати кілька embedding models.

5. **Latency**
   - Рішення: кешувати embeddings, використовувати lightweight models, додати p95 у report.

## Що показати на захисті

Обов'язково показати:

- UI chat;
- Qdrant tenant filter;
- LangGraph graph flow;
- MCP tool call;
- LangSmith/Phoenix trace;
- eval table;
- приклад cross-lingual retrieval;
- приклад tenant isolation.

## Чому це хороший курсовий проєкт

Цей проєкт добре демонструє навички AI Engineer:

- RAG pipeline;
- vector search;
- multi-tenancy;
- LangGraph agents;
- MCP integrations;
- cross-lingual retrieval;
- eval and observability;
- production-style API architecture.

Це виглядає сильніше, ніж звичайний "чат з PDF", бо система спроєктована як extensible platform, а не одноразове demo.
