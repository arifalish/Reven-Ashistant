with open('core/blackboard_memory.py', 'r') as f:
    content = f.read()

new_fields = """
    # Dynamic Routing & Reporting
    next_nodes: List[str] = Field(default_factory=list)
    general_response: str = Field(default="")
    final_report: str = Field(default="")
"""

if 'next_nodes: List[str]' not in content:
    content = content.replace(
        'final_artifacts: Dict[str, Any] = Field(default_factory=dict)',
        'final_artifacts: Dict[str, Any] = Field(default_factory=dict)' + new_fields
    )
    with open('core/blackboard_memory.py', 'w') as f:
        f.write(content)
