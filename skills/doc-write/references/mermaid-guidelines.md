# Mermaid diagram guidelines

The rules for keeping the quality of the Mermaid diagrams an LLM generates.

## Basic rules

### The node-count limit

- **At most 12 nodes per diagram** — beyond that, the layout tends to collapse
- When it would exceed 12 nodes, split the diagram

### The splitting strategy

- Split the diagram by layer (for example, a whole-architecture diagram + a detail diagram per layer)
- When a flow diagram runs long, split it by phase
- Give the split diagrams sequential numbers and titles (for example, `Figure 1: the overall flow`, `Figure 2: the authentication phase in detail`)

### Shortening labels

- Aim for **at most 20 characters** in a node label
- Write long explanations outside the node (in the surrounding text)
- Give the full name alongside an abbreviation at its first appearance

## The kinds of diagram and when to use them

| Diagram kind | Purpose | Recommended node count |
|----------|------|-------------|
| `flowchart` | A process or workflow | 5-10 |
| `sequenceDiagram` | Exchanges between APIs or components | 3-6 participants |
| `classDiagram` | A data model or class structure | 4-8 |
| `stateDiagram-v2` | State transitions | 4-8 |
| `erDiagram` | A DB schema | 4-8 |
| `graph TD` | Dependencies or a hierarchy | 6-12 |

## Anti-patterns

- Do not put a line break or a long sentence inside a node
- Nest subgraphs at most 2 levels deep
- Keep arrow labels minimal (omit one when the meaning carries without it)
- Use at most 3-4 colors (too many makes it harder to read, not easier)

## Verification points

After generating, self-check the following:

1. Is the node count within the limit?
2. Are the labels short and readable?
3. Does the diagram alone convey the gist (the details may be left to the text)?
4. Are there any Mermaid syntax errors?
