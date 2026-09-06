# Quickstart

The current `0.1.0a1` release exposes the first core primitives.

```python
from datetime import UTC, datetime

from pycrmkit import __version__
from pycrmkit.core import EntityId, FixedClock, UUID4Factory

factory = UUID4Factory()
entity_id = factory.new(EntityId)
clock = FixedClock(datetime(2026, 9, 6, 10, 0, tzinfo=UTC))

print(__version__)
print(entity_id)
print(clock.now())
```

The CRM facade and Contact domain arrive in the next `0.1.x` implementation milestones.
