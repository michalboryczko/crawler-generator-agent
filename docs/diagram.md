# Crawler Agent Architecture

Component-level architecture diagram showing the multi-agent web crawler system.

## System Overview

```mermaid
flowchart TB
    subgraph Entry["Entry Points"]
        main["main.py"]
        cli["CLI Arguments"]
    end

    subgraph Agents["Agent Core"]
        direction TB
        MainAgent["MainAgent<br/>(Orchestrator)"]
        BrowserAgent["BrowserAgent<br/>(Navigation)"]
        SelectorAgent["SelectorAgent<br/>(CSS Discovery)"]
        AccessAgent["AccessibilityAgent<br/>(HTTP Check)"]
        DataPrepAgent["DataPrepAgent<br/>(Test Data)"]
        BaseAgent["BaseAgent<br/>(Abstract)"]
        AgentResult["AgentResult<br/>(Data Contract)"]
    end

    subgraph Tools["Tools Layer"]
        direction TB
        subgraph MemTools["Memory Tools"]
            MemRead["MemoryReadTool"]
            MemWrite["MemoryWriteTool"]
            MemSearch["MemorySearchTool"]
            MemDump["MemoryDumpTool"]
        end
        subgraph BrowserTools["Browser Tools"]
            Navigate["NavigateTool"]
            Click["ClickTool"]
            Query["QuerySelectorTool"]
            Wait["WaitTool"]
        end
        subgraph ExtractTools["Extraction Tools"]
            BatchFetch["BatchFetchURLsTool"]
            BatchListings["BatchExtractListingsTool"]
            BatchArticles["BatchExtractArticlesTool"]
        end
        subgraph OtherTools["Other Tools"]
            FileCreate["FileCreateTool"]
            FileReplace["FileReplaceTool"]
            RandomChoice["RandomChoiceTool"]
            HTTP["HTTPRequestTool"]
        end
        subgraph OrchTools["Orchestration Tools"]
            RunBrowser["RunBrowserAgentTool"]
            RunSelector["RunSelectorAgentTool"]
            RunAccess["RunAccessibilityAgentTool"]
            RunDataPrep["RunDataPrepAgentTool"]
        end
        subgraph PlanTools["Plan Tools"]
            GenPlan["GeneratePlanTool"]
            GenTest["GenerateTestPlanTool"]
        end
    end

    subgraph Prompts["Prompts System"]
        direction TB
        Provider["PromptProvider"]
        Registry["PromptRegistry"]
        Template["PromptTemplate<br/>(Jinja2)"]
        subgraph DynTemplates["Dynamic Templates"]
            PaginationT["pagination_pattern"]
            ArticleExtT["article_extraction"]
            ListingExtT["listing_url_extraction"]
            ArticleUrlT["article_url_pattern"]
            SelectorAggT["selector_aggregation"]
        end
    end

    subgraph Core["Core Infrastructure"]
        direction TB
        LLM["LLMClient<br/>(OpenAI Wrapper)"]
        Browser["BrowserSession<br/>(CDP Client)"]
        Config["Config<br/>(Environment)"]
        HTMLClean["HTMLCleaner<br/>(Token Reduction)"]
    end

    subgraph Storage["Storage Layer"]
        direction TB
        MemoryStore["MemoryStore<br/>(Isolated)"]
        Backend["StorageBackend<br/>(Abstract)"]
        InMemory["InMemoryBackend"]
        MySQL["MySQLBackend"]
    end

    subgraph Observe["Observability"]
        direction TB
        Decorators["@traced_agent<br/>@traced_tool"]
        Logging["Structured Logging"]
        JSONL["JSONL Output"]
        OTEL["OpenTelemetry<br/>(Optional)"]
    end

    subgraph External["External Systems"]
        OpenAI["OpenAI API"]
        Chrome["Chrome DevTools<br/>(CDP)"]
        MySQLDB["MySQL Database"]
        Target["Target Website"]
    end

    %% Entry flow
    cli --> main
    main --> MainAgent

    %% Agent hierarchy
    MainAgent --> BrowserAgent
    MainAgent --> SelectorAgent
    MainAgent --> AccessAgent
    MainAgent --> DataPrepAgent
    BrowserAgent --> BaseAgent
    SelectorAgent --> BaseAgent
    AccessAgent --> BaseAgent
    DataPrepAgent --> BaseAgent
    BaseAgent --> AgentResult

    %% Agent to Tools
    MainAgent --> MemTools
    MainAgent --> OrchTools
    MainAgent --> PlanTools
    MainAgent --> FileCreate
    MainAgent --> FileReplace
    BrowserAgent --> BrowserTools
    BrowserAgent --> MemTools
    SelectorAgent --> BrowserTools
    SelectorAgent --> MemTools
    AccessAgent --> HTTP
    AccessAgent --> MemTools
    DataPrepAgent --> ExtractTools
    DataPrepAgent --> RandomChoice
    DataPrepAgent --> MemTools

    %% Tools to Core
    BrowserTools --> Browser
    ExtractTools --> LLM
    OrchTools --> AgentResult

    %% Prompts flow
    BaseAgent --> Provider
    Provider --> Registry
    Provider --> Template
    Template --> DynTemplates

    %% Core to External
    LLM --> OpenAI
    Browser --> Chrome
    Chrome --> Target

    %% Storage flow
    MemTools --> MemoryStore
    MemoryStore --> Backend
    Backend --> InMemory
    Backend --> MySQL
    MySQL --> MySQLDB

    %% Observability
    BaseAgent --> Decorators
    Decorators --> Logging
    Logging --> JSONL
    Logging --> OTEL

    %% Config
    Config --> LLM
    Config --> Browser
    Config --> Backend
```

## Component Descriptions

| Component | Purpose |
|-----------|---------|
| **MainAgent** | Orchestrates workflow: site analysis, selector discovery, accessibility check, test data prep |
| **BrowserAgent** | Navigates pages, extracts links, handles pagination using CDP |
| **SelectorAgent** | Discovers and validates CSS selectors for listings and articles |
| **AccessibilityAgent** | Tests if site works without JavaScript via HTTP requests |
| **DataPrepAgent** | Creates test datasets by sampling pages and extracting content |
| **BaseAgent** | Abstract base with tool execution loop and observability |
| **AgentResult** | Typed data contract for inter-agent communication |
| **PromptProvider** | Central access point for all prompts and templates |
| **PromptRegistry** | Versioned storage for static agent prompts |
| **PromptTemplate** | Jinja2-based dynamic prompt rendering |
| **MemoryStore** | Isolated key-value storage per agent |
| **StorageBackend** | Abstract interface for persistence (InMemory/MySQL) |
| **LLMClient** | OpenAI API wrapper with retry logic |
| **BrowserSession** | Chrome DevTools Protocol client for browser automation |
| **Observability** | @traced_agent/@traced_tool decorators for structured logging |

## Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Main as MainAgent
    participant Browser as BrowserAgent
    participant Selector as SelectorAgent
    participant Access as AccessibilityAgent
    participant DataPrep as DataPrepAgent
    participant Files as Output Files

    User->>Main: create_crawl_plan(url)

    Main->>Browser: Extract article links & pagination
    Browser-->>Main: AgentResult(links, pagination_type, max_pages)

    Main->>Selector: Find CSS selectors
    Selector-->>Main: AgentResult(listing_selectors, article_selectors)

    Main->>Access: Check HTTP accessibility
    Access-->>Main: AgentResult(http_accessible, requires_js)

    Main->>DataPrep: Create test dataset
    DataPrep-->>Main: AgentResult(listing_count, article_count)

    Main->>Files: Generate plan.md, test.md, test_set.jsonl
    Main-->>User: AgentResult(success, summary)
```

## Memory Isolation

Each agent operates with an isolated MemoryStore to prevent implicit data sharing:

```
MainAgent (orchestrator memory)
    ├── BrowserAgent (isolated memory)
    ├── SelectorAgent (isolated memory)
    ├── AccessibilityAgent (isolated memory)
    └── DataPrepAgent (isolated memory)
```

Data flows explicitly via:
1. **AgentResult.data** - Structured return values
2. **Context parameters** - Passed when running sub-agents
3. **Orchestrator memory** - Optional shared storage via `store_keys`
