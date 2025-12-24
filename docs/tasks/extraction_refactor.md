  Problem

  Content extraction only returns the first paragraph instead of all text from the matched container.

  Root Cause

  Selectors are discovered but never executed in Python code. They're passed as text hints to the LLM, which interprets "extract content" as "get first paragraph" instead of "get all text".

  Solution

  Apply selectors in Python code before sending to LLM:

  # Current flow:
  HTML (150KB) + selector hints → LLM → extracts first paragraph only

  # Fixed flow:
  HTML → BeautifulSoup.select(selector) → element.get_text() → LLM → formats/cleans

  Implementation Steps

  1. Modify RunExtractionAgentTool.execute() in src/tools/extraction.py:
    - Use BeautifulSoup to apply each selector from detail_selectors
    - Extract element.get_text(separator=' ', strip=True) for each field
    - Pass pre-extracted text to LLM for formatting/cleaning only
  2. Update the extraction prompt to reflect new role:
    - LLM now receives pre-extracted text, not raw HTML
    - Task changes from "find and extract" to "format and validate"
  3. Benefits:
    - Deterministic selector application (no LLM interpretation)
    - Smaller LLM input (text only, not 150KB HTML)
    - All content from container is captured
    - Faster, cheaper, more reliable


We have also adjust contract for data prep agent because now we have to pass all selectors disovered by selector agent we should pass them in contract in same way as we have in plan generator agent input with same level of decription detail and with relevant information in main agent prompt to be aware that is critical.
We should also implement our tool for batch extraction to works currently with memory keys and it also should has defined detailed input contract with related description for data prep agent which witch will ensure that tool will recive all selectors in correct way and it will be able to handle them. as example check crawler configuration tool
