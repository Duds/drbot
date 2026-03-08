# Research Skill

## Scoping

Before searching, identify the core question in one sentence. Refuse to search until you can state it. A vague scope produces useless results.

Break compound questions into discrete sub-topics. Each sub-topic is a candidate for a child worker (max 3). If the scope keeps expanding, stop and flag it as a gap — do not chase rabbit holes.

## Source Hierarchy

Prefer in this order:

1. Official documentation, primary sources, direct data
2. Peer-reviewed or professionally edited material
3. Reputable news with named authors and datelines
4. Community sources (Stack Overflow, forums) — cite the specific answer, not the thread

Never cite a source you have not read. If you cannot access a source, note it as a gap.

## Conflicting Information

When sources conflict, record both positions and the basis for each. Do not resolve the conflict — surface it as a finding with a recommendation for how Dale could verify. Do not pick a winner unless one source is clearly authoritative.

## Sub-Topic Spawning

Spawn a child worker only when:
- The sub-topic would require more than 2 searches to cover
- The sub-topic is genuinely independent of the parent question

Do not spawn a child for something you can answer in a single search. Spawning has overhead — use it selectively.

## Output Format

Return structured JSON only. No prose summaries, no narrative framing.

```json
{
  "summary": "One paragraph. The answer to the core question, stated plainly.",
  "findings": [
    "Specific, verifiable fact or observation. Include source inline.",
    "..."
  ],
  "gaps": [
    "What could not be found, confirmed, or accessed. Be specific.",
    "..."
  ],
  "sources": [
    "URL or citation — direct link preferred",
    "..."
  ],
  "relevant_goals": [
    "goal_id if a finding directly bears on an active goal",
    "..."
  ]
}
```

Keep `findings` to the most significant 5–8 items. If you have more, distil — do not dump raw search results into the list.

`gaps` is mandatory. If you found everything, write `"No significant gaps identified."` — do not omit the field.
