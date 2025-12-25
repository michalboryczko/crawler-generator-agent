# Plan generator refactor.

## current issues
One of our main features if currently implemented in bad way.

The plan generator is hardcoded text generation in code coupled with very specifcs memory keys which may won't be always present.

That is very problematic because we have case like whole work has been handled but plan has been generated incorrectly.

## Sugested soliution

### Plan generator as agent:

1. Main agent as orchestrator should call plan generator tool but we should create a new intermediate agent called "Plan Generator Agent" which will be responsible for plan generation only.
2. This agent will have defined input contract as standard agent but will have also:
```json
{
  "target_url": "string",
  "task_name": "string",
  "collected_information": [
    {
      "agent_name": "string",
      "output": {
        // object as whole json object from that agent includint response content and all fields
      },
      "description": "string - for example something like: Selector Agent: Here is the output from Selector Agent which includes verified listing & pagination selectors, inferred detail-page selectors these selector can be used in the crawl plan generation."
    }
  ]
}
```

3. that should be mapped with prompt templates to md file represenation as user prompt
```markdown
# Collected information for {{ target_url }} - Task: {{ task_name }}
for each item in collected_information:
## From {{ agent_name }}
### Description
{{ description }}
### Output

{{output.agent_output_response}}

create nested list base on json given in output - so we should have something like mardkown representation of json object

rest of prompt
```


4. We should have also defined correct systme prompt for that agent.
5. Agent should pass some draft of generic plan to llm as a example..
6. To provide exmaple of draft we should implement tool plan_draft_provider_tool or something like that that will allow us to keep beter flexibility and we will be able to improve that over time.
7. we should base on that what was currently our targert check examples/example_one/plan.md. 
8. That agent should have also another tool called prepare_crawler_configuration. which will be responsible for generation json which will be equivalent of that:
```json
{
    "start_url": "https://pism.pl/publikacje",
    "listing": {
        "container_selector": "div.articles.index.content",  # Focus on main content
        "article_link_selector": "div.article-preview div.article-title > a[href^="/publikacje/"]",
    },
    "pagination": {
        "enabled": false,
        "selector": "None",
        "type": "none",
        "strategy": "follow_next",
        "max_pages": 100
    },
    "detail": {
        "date": [".article-header .date"],
        "lead": [".article-header .lead"],
        "files": [".article-footer .files-content a[href$='.pdf'], .article-footer .files-content a[href$='.doc'], .article-footer .files-content a[href$='.docx'], .article-footer .files-content a[href$='.xls'], .article-footer .files-content a[href$='.xlsx'], .article-footer .files-content a[href$='.zip']", ".article-footer .files-content ul li a", ".article a[href$='.pdf'], .article a[href$='.doc'], .article a[href$='.docx'], .article a[href$='.xls'], .article a[href$='.xlsx'], .article a[href$='.zip']", "a[href$='.pdf'], a[href$='.doc'], a[href$='.docx'], a[href$='.xls'], a[href$='.xlsx'], a[href$='.zip']"],
        "title": [".article-header h1.title"],
        "images": [".article .picture img", ".article .content .richtext-preview img"],
        "authors": [".article-header .author a"],
        "content": [".article .content .richtext-preview", ".content .richtext-preview"]
    },
    "request": {
        "requires_browser": true,
        "wait_between_requests": 2,
        "max_concurrent_requests": 4,
        "timeout_seconds": 15
    },
    "deduplication": {
        "key": "url"
    }
}
```
so plan agent should pass all required data to that tool and it will generate that json. But we do not want to have it hardcoded at all that tool can pass that example and provide very good description for agent to understand what to pass.
But we do not want to hrdcode these fields:
```markdown
    "listing": {
        "container_selector": "div.articles.index.content",  # Focus on main content
        "article_link_selector": "div.article-preview div.article-title > a[href^="/publikacje/"]",
    },
    "detail": {
        "date": [".article-header .date"],
        "lead": [".article-header .lead"],
        "files": [".article-footer .files-content a[href$='.pdf'], .article-footer .files-content a[href$='.doc'], .article-footer .files-content a[href$='.docx'], .article-footer .files-content a[href$='.xls'], .article-footer .files-content a[href$='.xlsx'], .article-footer .files-content a[href$='.zip']", ".article-footer .files-content ul li a", ".article a[href$='.pdf'], .article a[href$='.doc'], .article a[href$='.docx'], .article a[href$='.xls'], .article a[href$='.xlsx'], .article a[href$='.zip']", "a[href$='.pdf'], a[href$='.doc'], a[href$='.docx'], a[href$='.xls'], a[href$='.xlsx'], a[href$='.zip']"],
        "title": [".article-header h1.title"],
        "images": [".article .picture img", ".article .content .richtext-preview img"],
        "authors": [".article-header .author a"],
        "content": [".article .content .richtext-preview", ".content .richtext-preview"]
    }
```
for listing and detail. That should work as dynamic collection so correct output will be like:
```json
{
    "listing": [
        {"property": "container_selector", "selectors": ["div.articles.index.content"]},
        {"property": "article_link_selector", "selectors": ["div.article-preview div.article-title > a[href^=\"/publikacje/\"]"]}
        // generated dynamically based on collected information
    ],
    "detail": [
      {"property": "date", "selectors": [".article-header .date"]},
        {"property": "files", "selectors": [".article-footer .files-content a[href$='.pdf'], .article-footer .files-content a[href$='.doc'], .article-footer .files-content a[href$='.docx'], .article-footer .files-content a[href$='.xls'], .article-footer .files-content a[href$='.xlsx'], .article-footer .files-content a[href$='.zip']", ".article-footer .files-content ul li a", ".article a[href$='.pdf'], .article a[href$='.doc'], .article a[href$='.docx'], .article a[href$='.xls'], .article a[href$='.xlsx'], .article a[href$='.zip']", "a[href$='.pdf'], a[href$='.doc'], a[href$='.docx'], a[href$='.xls'], a[href$='.xlsx'], a[href$='.zip']"]},
        {"property": "content", "selectors": [".article .content .richtext-preview", ".content .richtext-preview"]}
      ...
        // generated dynamically based on collected information
    ]
}
```
for detail and listign in description pass examples of possible properties but also informatioin that it should base on collected information and add for every discovered property selectors.
That tool should have correct contract to handle that.

Planner Generator agent should analyze provided data and create that plan in memory + dump it to file plan.md in task directory.

As output it should pass status and not whole plan but path to generated plan file - then main agent should show info like "Everything is ready plan has been generated and saved to {path}"

## Supervisor tool:

Create suppervisor tool which will be LLM based tool which should be used by agents to verify if they work is correct.

So currently we have static result validation in case of consitency with our schemas but we should add also logic validation which will check content. 
In that iteration we should apply that tool only to plan generator agent.

So when agent has to prepare some final results it should call that tool passing:
- summarized context 
- whole input provided to agent
- generate output candidate
- and given task description what is expected - that should be generated by agent - it will se in tool contract that it required field let say "given_task"  and description will be like "I got task to generate crawl plan for given target url based on collected information from other agents. The plan should include recommended fields and crawler configuration in json format."
- that tool in user prompt will have something like:
```markdown
 Please verify if provided output is correct and meets the requirements of the task.
    Here is the task description:
    {{ given_task }}
    Here is the input provided to the agent:
    {{ input_data }}
    Here is the output generated by the agent:
    {{ output_data }}
    Here is the context available to the agent:
    {{ context_data }}
    Please analyze the output and provide feedback on its correctness, completeness, and relevance to the task.
    ....
```
create also correct system prompt for that tool.


## Implementation
1. You do not care about backward compatibility because current implementation is broken. So do not add any code to ensure support and delete whole dead code.
2. Create new agent Plan Generator Agent with defined input contract and output contract.
3. Remember about our architecture concepts like:
    - set up correct observibility (logging, tracing, metrics)
    - apply possibility of using multi model configuration which we currently have
    - contracts as files
    - testing etc
    - every prompt should be as template file
