# Agent user context

currently we are not supporting user context in agents. This document describes how to implement user context support for agents.

## how it works no

we are passing kargs to agent_tool but we are checking only for `context`, `task` and `run_identifier` keys.

Parent aggent do not pass context keys int pass all keys on same level.

## what we should do

we should check in agent tool if there are more kargs passed besides `task` and `run_identifier` and if yes we should merge them into context dict.

so on entry wy may have something like:

```python
{
   "task": "Generate Crawl Plan",
   "run_identifier": "12345",
   "target_url": "https://example.com",
   "user_preferences": {
       "language": "en",
       "detail_level": "high"
   },
   "previous_attempts": [
       {"date": "2024-01-01", "result": "failed"},
       {"date": "2024-02-01", "result": "partial"}
   ]
}
```

then context passed to agent will be:

```python
{
   "target_url": "https://example.com",
   "user_preferences": {
       "language": "en",
       "detail_level": "high"
   },
   "previous_attempts": [
       {"date": "2024-01-01", "result": "failed"},
       {"date": "2024-02-01", "result": "partial"}
   ]
}
```


## context parsing in prompt templates

We should add method in base agent tool to apply whole given context as json into user prompt as


```markdown
{{task}} 

Context:
```json
{{ context | tojson }}
```
```

task is task from parent agent that means that is that what we are providing now as task karg.
This way agent will have full context available for decision making.
remeber about use template

### for plan generator agent use a litte bit different approach
overwrite method created above to and use template which have describer in plan_generator_refactor.md in point 3
check template which we have currently in src/prompts/templates/agents/plan_generator_user.md.j2 and


example for collected_information should be generated from context key called `collected_information`

```json
[
  {
    "agent_name": "discovery_agent",
    "description": "Discovered interactive elements and page structure for login form",
    "output": {
      "page_title": "Login - MyApp",
      "discovered_elements": [
        {
          "element_id": "email-input",
          "type": "input",
          "attributes": {
            "name": "email",
            "placeholder": "Enter email",
            "required": true
          },
          "validation_rules": ["email_format", "not_empty"]
        },
        {
          "element_id": "password-input",
          "type": "input",
          "attributes": {
            "name": "password",
            "type": "password",
            "required": true
          },
          "validation_rules": ["min_length_8"]
        }
      ],
      "forms_detected": 1,
      "metadata": {
        "scan_duration_ms": 234,
        "framework_detected": "React"
      }
    }
  },
  {
    "agent_name": "selector_agent",
    "description": "Generated robust CSS and XPath selectors for identified elements",
    "output": {
      "selectors": {
        "email-input": {
          "primary": {
            "css": "#email-input",
            "xpath": "//input[@id='email-input']",
            "confidence": 0.95
          },
          "fallback": [
            {
              "css": "input[name='email']",
              "confidence": 0.85
            },
            {
              "css": "form input:first-child",
              "confidence": 0.60
            }
          ]
        },
        "password-input": {
          "primary": {
            "css": "#password-input",
            "xpath": "//input[@type='password']",
            "confidence": 0.98
          },
          "fallback": []
        }
      },
      "strategy": "id-first-with-attribute-fallback",
      "warnings": []
    }
  },
  {
    "agent_name": "accessibility_agent",
    "description": "Accessibility audit results with WCAG compliance scores",
    "output": {
      "overall_score": 78,
      "compliance_level": "AA",
      "issues": [
        {
          "severity": "critical",
          "wcag_criterion": "1.1.1",
          "affected_elements": ["logo-image"],
          "recommendation": "Add alt text to image",
          "auto_fixable": true
        },
        {
          "severity": "warning",
          "wcag_criterion": "2.4.6",
          "affected_elements": ["submit-btn"],
          "recommendation": "Improve button label descriptiveness",
          "auto_fixable": false
        }
      ],
      "passed_checks": {
        "keyboard_navigation": true,
        "color_contrast": true,
        "focus_indicators": false
      },
      "audit_metadata": {
        "tool_version": "1.2.0",
        "rules_applied": 56,
        "elements_scanned": 124
      }
    }
  }
]
```

should be parsed ass 
```markdown

# Collected information for https://myapp.com/login - Task: login_form_automation

## From discovery_agent

### Description
Discovered interactive elements and page structure for login form

### Output

- **page_title**: Login - MyApp
- **discovered_elements**:
  - [0]:
    - **element_id**: email-input
    - **type**: input
    - **attributes**:
      - **name**: email
      - **placeholder**: Enter email
      - **required**: true
    - **validation_rules**:
      - email_format
      - not_empty
  - [1]:
    - **element_id**: password-input
    - **type**: input
    - **attributes**:
      - **name**: password
      - **type**: password
      - **required**: true
    - **validation_rules**:
      - min_length_8
- **forms_detected**: 1
- **metadata**:
  - **scan_duration_ms**: 234
  - **framework_detected**: React

---

## From selector_agent

### Description
Generated robust CSS and XPath selectors for identified elements

### Output

- **selectors**:
  - **email-input**:
    - **primary**:
      - **css**: #email-input
      - **xpath**: //input[@id='email-input']
      - **confidence**: 0.95
    - **fallback**:
      - [0]:
        - **css**: input[name='email']
        - **confidence**: 0.85
      - [1]:
        - **css**: form input:first-child
        - **confidence**: 0.60
  - **password-input**:
    - **primary**:
      - **css**: #password-input
      - **xpath**: //input[@type='password']
      - **confidence**: 0.98
    - **fallback**: *(empty)*
- **strategy**: id-first-with-attribute-fallback
- **warnings**: *(empty)*

---

## From accessibility_agent

### Description
Accessibility audit results with WCAG compliance scores

### Output

- **overall_score**: 78
- **compliance_level**: AA
- **issues**:
  - [0]:
    - **severity**: critical
    - **wcag_criterion**: 1.1.1
    - **affected_elements**:
      - logo-image
    - **recommendation**: Add alt text to image
    - **auto_fixable**: true
  - [1]:
    - **severity**: warning
    - **wcag_criterion**: 2.4.6
    - **affected_elements**:
      - submit-btn
    - **recommendation**: Improve button label descriptiveness
    - **auto_fixable**: false
- **passed_checks**:
  - **keyboard_navigation**: true
  - **color_contrast**: true
  - **focus_indicators**: false
- **audit_metadata**:
  - **tool_version**: 1.2.0
  - **rules_applied**: 56
  - **elements_scanned**: 124
```


of course remember about task on top of that.