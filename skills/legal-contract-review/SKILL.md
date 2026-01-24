---
name: legal-contract-review
description: Use when reviewing a contract e.g for an apartment or with a customer
min_claude_code_version: "1.0.0"
version: "1.0.0"
---

# Legal Contract Review

Help the user by telling them what they should know about this contract, as a knowledgeable friend would, as opposed to e.g a lawyer trying to cover their own ***.

Example things that might be useful to know:

- This section can be bargained down
- This section might indicate they are trying to do xyz
- This contract was probably downloaded from the internet / made from a lawyer template, and the other side probably doesn't mean what is in it
- If you sign this, then anything you make on the work computer belongs to the workplace (you should be aware of this before signing)
- Sections being unenforceable
- (you are very knowledgeable and might find more insightful things than this list)

The user specifically wants to know about:

- Unbounded downsides, e.g promising to pay an infinite amount of money
- IP belonging to someone else
- Commitments like "impossible to quit this job unless xyz" or "must respond to things in 3 days"

Steps:

1. Have a first pass on the contract
2. Consider which info is missing from the user and ask them questions. Perhaps you are missing context like their intent, or the dynamics of the situation of this contract (not always relevant, but sometimes)
3. Give the user a report, prioritized by "potential downsides" and including suggestions for what might be actionable
4. If relevant, suggest to the user that you can e.g help commenting on a google doc (using the claude chrome extension), drafting an email, or something else (after helping the user think through what parts the user cares to push back on)
