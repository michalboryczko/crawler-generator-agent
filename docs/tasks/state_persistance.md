# Session state presistance
I would like to implement presistance for state of session.

So state of session is full context of each instance of each agent is given session.

Currently we have sessions and each for example memory entry in session is related to same session via id so we can check what was created and when.
I would like to have persistance for agent context.
  
## Requriements

1. Each agent instance should have its own context stored in db with relation to session
    - generate unique uuid for each agent instance on initialization
    - when we have multiple instances of same agent in one session each should have its own context
2. in context we should always have each input message system/user/assistant stored with timestamp and whole content!
3. we should have also all tool_calls from agent and tool_execution results
4. basicaly like now each we are sending to llm or retriving something we append object to our messages list then we are using that as context for next calls so now we should store that in db
5. we should store that in way will allow us to rerun session later with same context from specific point.
    - we should have option to --copy which will copy whole context and memory state from session and create new session with same data but until given point
    - we should have option to --overwrite which will erase all memory and context after given point and continue from there
    - we should have option to --resume which will continue from last point


## Architecture approach.

We should implement that as event sourcing. Each interaction with agent should be stored as event in db with relation to session and agent instance id.
so like when now we are adjusting messages list in agent run time we should do exactly same but we should have not just array but some context service etc.
And on re run we should apply all events from db to recreate context each event by each
## tips

remember about our arch aproach.