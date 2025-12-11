# Development plan

That document will describe future functionalities and improvements which we want to implement in the agent.


## Break changes:
- instead of single plan.md output we will have output directory for plan.
- inside that directory we will have multiple files:
    - plan.md - main plan description
    - test.md - test plan description
    - data/test_set.jsonl - prepared test dataset in jsonl format
- we do not want to pass output dir it should be generated via page url for example from `www.rand.org` - `rand_org/`
- we should be able to config in .env path to store these outputs - like `PLANS_OUTPUT_DIR=./plans_output/` - then final output dir will be `./plans_output/rand_org/`
- not code but main agent should be aware of these paths and use `file tool` to work with files inside that output dir
- only directory should be created after initialization via code
- as final step after aggent dumped all files inside output we should be able to config in .env templates path and code should copy with `-r` everything from that template path to output dir - so we can have some predefined files like README.md, .gitignore, requirements.txt etc


### agent flow changes

#### Workflow - current
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

#### Workflow - new
until point 8 is same
9. use `Accessibility validation agent` to check if we are able to access given website content with just http client like curl etc
10. use `Contract data preparation agent` to prepare test dataset for given website
11. main agent prepare final plan in markdown format with all necessary details to implement the crawler - also it should be aware of accessibility validation and add that information to plan if not it should add information exactly like this "Page require browser - you should use headfull-chrome API check docs/headfull-chrome.md for more details"
12. main agent prepare test plan in output dir in test.md file - it should contains information how to use prepared test dataset
13. main agent use `memory tool extension - dump memory function` to dump all prepared test data to `data/test_set.jsonl` file in output dir

## Agent Capabilities


### Contract data preparation agent

Agent should be able to provide contact test data for given side.

After understanding how to use website what selectors etc we should be able to prepare test dataset.

1. Fetch examples of listing pages html at least 5 different listing pages 
2. Fetch examples of article pages html at least 20 different article pages 
3. These pages should be fetched via browser agent. 
4. Their should be randomly picked to avoid overfitting to specific page structure. 
5. so we should use `random-choice` tool where we need to pass list of candidates for listing pages candidates should be generated using our logic which we extracted which allow us to create urls for listing pages. 
6. we should chose at least 5 different listing pages and open them and then via llm extract articles urls from them and pass all of them to random-choice tool to pick 20 different article pages - we need to wait with page selection until we will have all article urls from all listing pages. 
7. via llm extract data which we want to retrive from each html like article urls for listing pages and title, date, author, content for article pages 
8. store that data in memory tool:
    - stored data should be as test set
    - each entry should contain: 
        - type (listing or article)
        - given: html content
        - expected: extracted data in json format
    - We should use keys which allow to easy identification that are assigned to prepared test data - like `test-data-listing-1`, `test-data-article-1` etc
9. agent should also prepare some short description how to use test data etc - not to long - also store that in memory tool with key `test-data-description-1`


After that main agent will be aware of that tests so it should use `memory tool` function dump memory and dump all tests keys to jsonl file - we do not want to pass test content to model.
Main agent should be able to generate test plan which we will store in test.md file in plan output directory.

### file tool

1. tool should allows to create new file with given content and extension
2. it should allows to read content of given file with tail/head -n options
3. it should allows to append content to given file
4. it should allows to replace content of given file

### random-choice tool

Just simple random picker

It should accept list of candidates and number of items to pick and return randomly picked items from that list.


### memory tool extension - dump memory function 

Tool should allow to dump all given keys from memory to jsonl file

it should accept list of keys to dump and output file path

dump should be in jsonl format where each line is json object with only content of given key


### Accessibility validation agent:

Agent to check if we are able to access given website content with just http client like curl or requests library without javascript rendering 

it should be run after we collected knowladge how to use given website

It should use that knowladge to try fetch some pages via `HTTP request tool` and check if page is accessible via that method or we should use browser rendering to access that content

We need to store that information via `memory tool` and then main agent while plan generation should be aware of that information and add information about that in plan content

### HTTP request tool:

Tool should allow to perform http requests with given method, headers, body etc

it should return response status code, headers and body



## TESTS

1. Create unit tests for existing and new tools and agents
2. Create integration tests for whole agent flow if we can mock everything