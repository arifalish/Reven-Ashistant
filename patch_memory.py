with open('core/blackboard_memory.py', 'r') as f:
    content = f.read()

if 'opendots_log: str = Field(default="")' not in content:
    content = content.replace(
        'replica_codebase: Dict[str, str] = Field(default_factory=dict)',
        'replica_codebase: Dict[str, str] = Field(default_factory=dict)\n    opendots_log: str = Field(default="")'
    )
    with open('core/blackboard_memory.py', 'w') as f:
        f.write(content)
