# Self creating crawler agen

## Key points

In that stage we want to create basic agent which will be able to understand how to create web crawler for given website.

It should create detailed plan which we will use to implement the crawler using claude code.

## Technical concepts

1. We should use OpenAI client becase their api provide standart which has been implemented by other vendors like claude.
2. We should use markdown format to create the plan.
3. We should delegate tasks to specialized agents when needed to decrease complexity of the main agent and avoid context overload.

### Main agent

The main agent will be responsible for:
1. Receiving the URL of the website to be crawled.
2. Basic website interactions via chrome devtools mcp. 
3. We should not load direct tools from mcp devtools but instead create specialized agents/tools which will use mcp to perform specific tasks.
4. chrome instance should be keep live until we finish the plan and should be accessible by all specialized agents.
5. As final result we should have plan which will contains all necessary information to implement the crawler
    - article links selectors - for example css selector of xpath (e.g. ".article-list .article-item a.href")
    - pagination type and how to use it (e.g. "?page={n}" or ?"offset={n*20}")
    - User-Agent and other necessary headers

### Specialized agents/tools
#### Memory tool:
Tool should be use by agents to store and retrieve information during the planning process.

- for now use runtime memory only (in-memory dictionary)

#### Browser interaction agent:
That agent should be use by agents to interact with the website via chrome devtools mcp.
Use also OpenAI client

Tool is for interacting with browser and verify results of the interaction.

- Use to load given page so call BrowserAgent with interact type "load_page" and url parameter.
- Use to click on given selector so call BrowserAgent with interact type "click" and selector parameter.

Each call required context which we should use to verify the result of the interaction that context should be pass to verify tool.

Agent should return success or failure.

we should use memory tool to store url, content before - if no content before then null, content after - if no content after then null, timestamp, url

We should wait at least 5s after action before verifying the result.

- verify tool:
    - requires verification before interaction url,content and after interaction url,content
    - returns success status and short description of the verification


#### Selector tool:
Tool should be use by 

- Responsible for finding the article links selectors
- Responsible for finding selector which we have to click to load more articles/go to next page

It should works like this:
1. main agent - "how to go to next page?
2. selector tool - get current page content from browser via get content mcp to devtools or from memory tool if already stored
3. selector tool - send content + question to OpenAI client to find the selector
4. selector tool - return selector to main agent

Use also memory tool to store found selectors

For article links selector:

1. main agent - "How I can extract article links from the page?"
2. selector tool - get current page content from browser via get content mcp to devtools or from memory tool if already stored
3. selector tool - send content + question to OpenAI client to find the selector
4. selector tool - selector verification tool if ok return selector to main agent if not repeat from step 2 with updated question (question + optuput from verification tool)

use also memory tool to store found selectors

selector verification tool:
1. requires selector and page content
2. expected results - llm before call that tool should extract on own side articles links it should be sure of that
3. then we should run code which will use these selector and compare results with expected results
4. if success return success status else return failure status with description what is wrong


### Workflow
1. main agent - receive url to crawl
2. main agent - load the page via browser interaction agent
3. main agent - ask selector tool to check how to go to next page
4. main agent - use interaction browser agent to click on new page selector
5. main agent - "ok I see new page loaded, now I want to find article links selector"
6. main agent - use selector tool to find article links selector
7. main agent - ok now I have all time to summarize
  - from memory tool get visited pages urls
  - from memory tool get article links selector
8. main agent - Ok I visited N pages with urls: [...], I see pagination is by url parameter "?page={n}", because second page url is "..." when I click on "..." selector, I found article links selector is "...", so I need to plan use that pagination and that selector.
9. main agent - create final plan in markdown format with all necessary details to implement the crawler
