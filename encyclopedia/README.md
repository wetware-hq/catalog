# Encyclopedia catalog (v0.1)

Plain-file catalog with one CLI (`catalog`). Each field cites a content-addressed source snapshot; `catalog lint` enforces evidence match and schema conformance [2][19].

See `ARCHITECTURE.md` and `architecture.mmd` for the pipeline diagram.

```bash
cd encyclopedia && pip install -e ".[dev]"
catalog research --run-id RUN --url 'https://example.com/spec.txt'
catalog extract --draft catalog/pipeline/my.draft.json
catalog verify --draft catalog/pipeline/my.draft.json --out /tmp/verified.json
catalog write --verified /tmp/verified.json --run-id RUN
catalog dedup --run-id RUN
catalog references refresh && catalog lint --json
# Commit: one pipeline run → one commit; message lists entry ids touched.
catalog query get my-id --json
catalog query search 'keyword' --json
```

Aggregated citations: `REFERENCES.md` (sync checked by lint) [19].

## References

[2] WikiChat: Stopping the Hallucination of LLM Chatbots by Few-Shot Grounding on Wikipedia. Semnani et al., 2023. https://arxiv.org/abs/2305.14292  
[19] Skilldex: Package Manager and Registry for Agent Skill Packages. 2026. https://arxiv.org/abs/2604.16911  
