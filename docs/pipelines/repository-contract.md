# Pipeline Repository Contract

`PipelineRepository` is backend-neutral and must expose:

```text
get(id)
find(id)
save(pipeline)
list(page)
```

## Required behavior

Adapters must preserve:

- normalized stable pipeline IDs;
- complete ordered stage definitions;
- transition declarations;
- terminal outcomes and Decimal probability defaults;
- exact offset pagination;
- deterministic `id ASC` list ordering;
- `pipeline.not_found` semantics;
- copy isolation where the adapter stores mutable Python structures.

Repositories persist valid definitions. Transition validation remains a domain-service responsibility through `PipelineTransitionPolicy`; repositories must not invent or silently relax transition rules.

The official `MemoryPipelineRepository` executes the reusable repository contract suite.
