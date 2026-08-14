"""Fixed evaluation suite run against both agent versions during canary checks.

Deliberately exercises every tool path, including the flaky inventory
service, so the comparison reflects real reliability differences rather than
just raw model quality.
"""

EVAL_PROMPTS: list[str] = [
    "What is 842 * 17 - 96?",
    "Look up stock for SKU-1042 and tell me which warehouse has it.",
    "Search the web for the current version of the Python programming language.",
    "Check inventory for SKU-2071 and SKU-3399, then tell me the total units across both.",
    "What's (128 + 47) / 5, rounded to two decimal places?",
    "Search for who created the LangChain framework.",
    "Look up SKU-4410's stock level. If it's below 50 units, say we should reorder.",
    "What is 15% of 860?",
]
