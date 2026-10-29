# Multi-Model Arena Evaluation Skill

## Mission
Compare candidate answers or models using a fair, reproducible rubric.
## Workflow
1. Define task, evaluation criteria, weights and unacceptable failure modes before judging.
2. Multi-Model Evaluator: run only configured model endpoints; log model identity and failures.
3. Blind Judge Agent: assess anonymized candidates against the same rubric without relying on model labels.
4. Consensus Aggregator: compare score spread, cite concrete evidence and explain disagreement.
5. Quality gate: penalize unsupported claims and missing requirements; don't invent runs or scores.
## Output
Rubric, candidates evaluated, evidence-based scores, disagreement analysis, winner if justified, limitations and reproducible next test.