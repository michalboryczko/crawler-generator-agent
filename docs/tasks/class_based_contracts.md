1. we have schemas as json files only for agents we have to add them for each tool as separate file.
2. in get_parameters_schema for tool return json schema from file.
3. in tools replace defined arguments to *kwargs - we are sure that they are valid because we allways have validation before function call
4. when we unify all tools input to **kwargs we can enable override check again because or signature will be consistent
5. for agent tools input  we have to also move that to **kwargs + schema file etc

some of these methods are not in use at all or we are using them only in tests - we should not write code for tests but tests should cover the actual code used
```python


    @property
    def agent(self) -> "BaseAgent":
        """The wrapped sub-agent."""
        return self._agent

    @property
    def output_schema(self) -> dict[str, Any]:
        """The output contract schema."""
        return self._output_schema

    @property
    def input_schema(self) -> dict[str, Any] | None:
        """The input contract schema (if defined)."""
        return self._input_schema

    def get_agent_description(self) -> str:
        """Return agent's full description via agent's get_description method."""
        return self._agent.get_description()

    def get_tool_name(self) -> str:
        """Return the tool name (run_{agent.name})."""
        return self.name
```

7. that is also only for tests:
```python
    def prompt_attachment(self) -> str:
        """Generate prompt section describing this agent and its contracts.

        Returns a markdown-formatted string that can be included in prompts
        to describe the sub-agent's capabilities and expected output format.

        Returns:
            Markdown string with agent description and contracts
        """
        example_json = generate_example_json(self._output_schema)
        example_json_str = json.dumps(example_json, indent=2)

        lines = [
            f"### {self._agent.name}",
            f"**Tool name:** `{self.name}`",
            f"**Description:** {self._description}",
            "",
            "#### Output Contract",
            generate_fields_markdown(self._output_schema),
            "",
            "#### Example Output",
            "```json",
            example_json_str,
            "```",
        ]

        if self._input_schema:
            lines.extend(
                [
                    "",
                    "#### Input Contract",
                    generate_fields_markdown(self._input_schema),
                ]
            )

        return "\n".join(lines)
```