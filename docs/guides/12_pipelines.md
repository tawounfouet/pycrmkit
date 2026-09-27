# Pipelines

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 3 - Sales**.

Chapter 11 introduced Opportunity as the commercial outcome being pursued.
Pipeline adds the process that determines **where** that Opportunity is in the
sales journey and **which movements are allowed**.

The central question becomes:

~~~text
Through which ordered sales process does this Opportunity move?
~~~

## What you will build

You will define an immutable Pipeline, create ordered Stages, attach default
probabilities and terminal outcomes, declare explicit StageTransition edges, move
an Opportunity through the persisted Pipeline policy, inspect stage-entry time
and duration, and understand the repository and event boundaries.

By the end of the chapter:

~~~text
Opportunity
    |
    v
 Pipeline
    |
    +--> Stage
    |
    +--> StageTransition
    |
    +--> PipelineTransitionPolicy
              |
              v
        allowed movement
~~~

## 1. Why Pipeline exists

Opportunity owns the commercial outcome.

Pipeline owns the sales process.

~~~text
Opportunity
= what business outcome are we pursuing?

Pipeline
= through which process does it move?

Stage
= where is it now?

StageTransition
= where may it move next?
~~~

Keeping those concepts separate prevents sales-process configuration from being
hard-coded into Opportunity itself.

## 2. Pipeline is immutable

Pipeline is a frozen dataclass.

A Pipeline definition contains:

~~~text
id
name
stages
transitions
~~~

Once constructed, the definition is treated as immutable domain configuration.

PyCRMKit V1 exposes define/get/list, not in-place Pipeline editing.

## 3. Define a minimal Pipeline

~~~python
from pycrmkit import CRM
from pycrmkit.pipelines import Stage

crm = CRM.memory()

pipeline = crm.pipelines.define(
    id="sales",
    name="Sales",
    stages=(
        Stage(
            id="new",
            name="New",
            position=0,
        ),
    ),
)

assert pipeline.id == "sales"
assert pipeline.initial_stage.id == "new"
~~~

A Pipeline requires at least one Stage.

An empty stage collection raises:

~~~text
ValidationError
code = pipeline.stages.required
~~~

## 4. Pipeline IDs are stable keys

Pipeline IDs are normalized with Unicode NFKC, trimming and case-folding.

~~~python
pipeline = crm.pipelines.define(
    id=" SALES ",
    name="Enterprise Sales",
    stages=(
        Stage("new", "New", 0),
    ),
)

assert pipeline.id == "sales"
~~~

The normalized key must match a slug-like contract:

~~~text
first character:
a-z or 0-9

remaining characters:
a-z
0-9
.
_
-

maximum length:
120
~~~

Invalid values raise:

~~~text
ValidationError
code = pipeline.id.invalid
~~~

## 5. Pipeline names

Pipeline name is required and presentation-oriented.

~~~python
pipeline = crm.pipelines.define(
    id="enterprise",
    name="  Enterprise   Sales ",
    stages=(
        Stage("new", "New", 0),
    ),
)

assert pipeline.name == "Enterprise Sales"
~~~

The stable maximum length is 200 characters.

Blank values raise:

~~~text
pipeline.name.required
~~~

Overlong values raise:

~~~text
pipeline.name.too_long
~~~

## 6. Stage is a value object

A Stage contains:

~~~text
id
name
position
default_probability
terminal
outcome
~~~

Stage is also frozen.

Pipeline therefore contains an immutable ordered tuple of immutable Stage
definitions.

## 7. Stage IDs

Stage IDs use the same general stable-key model as Pipeline IDs.

~~~python
stage = Stage(
    id=" QUALIFIED ",
    name="Qualified",
    position=10,
)

assert stage.id == "qualified"
~~~

Invalid Stage keys raise:

~~~text
ValidationError
code = pipeline.stage.id.invalid
~~~

The maximum key length is 120 characters.

## 8. Stage names

Stage names are Unicode-normalized, trimmed and whitespace-collapsed.

~~~python
stage = Stage(
    "proposal",
    "  Proposal   Sent ",
    20,
)

assert stage.name == "Proposal Sent"
~~~

The stable maximum length is 160 characters.

Blank Stage names raise:

~~~text
pipeline.stage.name.required
~~~

## 9. Stage positions define ordering

position must be a non-negative integer.

~~~python
Stage(
    "new",
    "New",
    0,
)
~~~

Invalid examples:

~~~text
-1
1.5
True
~~~

raise:

~~~text
ValidationError
code = pipeline.stage.position.invalid
~~~

Boolean is deliberately not accepted merely because bool is an int subclass in
Python.

## 10. Pipeline sorts Stages by position

Callers do not have to provide Stages in final order.

~~~python
from pycrmkit.pipelines import Pipeline

pipeline = Pipeline(
    id="sales",
    name="Sales",
    stages=(
        Stage("proposal", "Proposal", 20),
        Stage("new", "New", 0),
        Stage("qualified", "Qualified", 10),
    ),
)

assert tuple(
    stage.id
    for stage in pipeline.stages
) == (
    "new",
    "qualified",
    "proposal",
)
~~~

Sorting uses:

~~~text
position ASC
id ASC
~~~

The position is the business ordering key.

## 11. Stage IDs must be unique

This is invalid:

~~~text
Stage("new", ..., 0)
Stage("new", ..., 10)
~~~

and raises:

~~~text
ValidationError
code = pipeline.stages.duplicate_id
~~~

## 12. Stage positions must be unique

This is also invalid:

~~~text
Stage("new", ..., 0)
Stage("qualified", ..., 0)
~~~

and raises:

~~~text
ValidationError
code = pipeline.stages.duplicate_position
~~~

A Pipeline therefore has one deterministic Stage at each declared position.

## 13. initial_stage

The first ordered Stage is the Pipeline initial Stage.

~~~python
assert pipeline.initial_stage.id == "new"
~~~

There is no separate initial_stage_id field in V1.

Initial-stage semantics are derived from ordered Stage definitions.

## 14. Find a Stage

~~~python
stage = pipeline.stage(" QUALIFIED ")

assert stage.id == "qualified"
~~~

Stage lookup normalizes the requested ID.

A missing Stage raises:

~~~text
NotFoundError
code = pipeline.stage.not_found
~~~

## 15. Stage default probability

A non-terminal Stage may declare an optional default probability:

~~~python
from decimal import Decimal

qualified = Stage(
    "qualified",
    "Qualified",
    10,
    default_probability=Decimal("0.35"),
)
~~~

The value must be:

~~~text
Decimal
finite
0 <= probability <= 1
~~~

A float raises:

~~~text
pipeline.stage.probability.decimal_required
~~~

An out-of-range or non-finite Decimal raises:

~~~text
pipeline.stage.probability.out_of_range
~~~

## 16. Stage probability is a default, not global truth

Stage.default_probability defines what Opportunity movement should apply when
the Stage is entered through Pipeline policy.

It does not mean every Opportunity in that Stage must always carry that exact
probability forever.

The distinction is:

~~~text
Stage.default_probability
= process default

Opportunity.probability
= current Opportunity state
~~~

## 17. Terminal Stages

A terminal Stage closes the Opportunity when entered through Pipeline movement.

~~~python
won = Stage(
    "won",
    "Won",
    90,
    terminal=True,
    outcome="won",
)
~~~

Terminal outcomes are:

~~~text
won
lost
cancelled
~~~

represented by StageOutcome.

## 18. StageOutcome

~~~python
from pycrmkit.pipelines import StageOutcome

assert StageOutcome.WON.value == "won"
assert StageOutcome.LOST.value == "lost"
assert StageOutcome.CANCELLED.value == "cancelled"
~~~

OpportunityStatus string values are compatible inputs at runtime because the
Stage constructor resolves the declared outcome through StageOutcome.

## 19. Terminal Stage requires an outcome

This is invalid:

~~~python
Stage(
    "done",
    "Done",
    90,
    terminal=True,
)
~~~

It raises:

~~~text
ValidationError
code = pipeline.stage.outcome.required
~~~

Terminal means a specific commercial closure, not merely "last in the list".

## 20. Non-terminal Stage cannot declare an outcome

This is also invalid:

~~~python
Stage(
    "qualified",
    "Qualified",
    10,
    terminal=False,
    outcome="won",
)
~~~

It raises:

~~~text
ValidationError
code = pipeline.stage.outcome.non_terminal
~~~

## 21. Terminal probability defaults

Terminal outcomes have canonical probability defaults.

~~~text
WON       -> Decimal("1")
LOST      -> Decimal("0")
CANCELLED -> Decimal("0")
~~~

Therefore:

~~~python
won = Stage(
    "won",
    "Won",
    90,
    terminal=True,
    outcome="won",
)

assert won.default_probability == Decimal("1")
~~~

and:

~~~python
lost = Stage(
    "lost",
    "Lost",
    100,
    terminal=True,
    outcome="lost",
)

assert lost.default_probability == Decimal("0")
~~~

## 22. Terminal probability consistency

A terminal Stage may explicitly provide its probability, but it must match the
outcome.

Invalid:

~~~text
WON + 0.80
LOST + 0.20
CANCELLED + 0.10
~~~

raises:

~~~text
ValidationError
code = pipeline.stage.probability.terminal_mismatch
~~~

## 23. StageTransition

StageTransition declares one directed edge:

~~~python
from pycrmkit.pipelines import StageTransition

transition = StageTransition(
    "new",
    "qualified",
)

assert transition.from_stage == "new"
assert transition.to_stage == "qualified"
~~~

Both endpoints are normalized as Stage IDs.

## 24. Transitions are directed

This:

~~~text
new -> qualified
~~~

does not imply:

~~~text
qualified -> new
~~~

If reverse movement is allowed, it must be declared explicitly.

Pipeline movement is a directed graph, not automatic adjacency.

## 25. Self-transition is invalid

~~~python
StageTransition(
    "proposal",
    "proposal",
)
~~~

raises:

~~~text
InvalidStageTransition
code = pipeline.transition.invalid
~~~

The error reason states that self-transition is not allowed.

## 26. Define a real sales Pipeline

~~~python
from decimal import Decimal

from pycrmkit.pipelines import (
    Stage,
    StageTransition,
)

pipeline = crm.pipelines.define(
    id="sales",
    name="Enterprise Sales",
    stages=(
        Stage(
            "new",
            "New",
            0,
            Decimal("0.10"),
        ),
        Stage(
            "qualified",
            "Qualified",
            10,
            Decimal("0.35"),
        ),
        Stage(
            "proposal",
            "Proposal",
            20,
            Decimal("0.65"),
        ),
        Stage(
            "won",
            "Won",
            90,
            terminal=True,
            outcome="won",
        ),
        Stage(
            "lost",
            "Lost",
            100,
            terminal=True,
            outcome="lost",
        ),
    ),
    transitions=(
        StageTransition(
            "new",
            "qualified",
        ),
        StageTransition(
            "qualified",
            "proposal",
        ),
        StageTransition(
            "proposal",
            "won",
        ),
        StageTransition(
            "proposal",
            "lost",
        ),
    ),
)
~~~

This definition is the process contract used by Opportunity movement.

## 27. Transition endpoints must exist

A Pipeline rejects transitions that reference unknown Stages.

~~~text
new -> missing
~~~

raises:

~~~text
ValidationError
code = pipeline.transition.stage_not_found
~~~

The error context contains from_stage and to_stage.

## 28. Duplicate transitions are invalid

Declaring the same pair twice:

~~~text
new -> qualified
new -> qualified
~~~

raises:

~~~text
ValidationError
code = pipeline.transitions.duplicate
~~~

## 29. Terminal Stages cannot have outgoing transitions

This definition is invalid:

~~~text
won -> reopened
~~~

when won is terminal.

Pipeline construction raises:

~~~text
ValidationError
code = pipeline.transition.from_terminal
~~~

This protects terminal semantics at configuration time.

## 30. Pipeline.allows()

Pipeline can answer a simple policy question:

~~~python
assert pipeline.allows(
    "new",
    "qualified",
) is True

assert pipeline.allows(
    "new",
    "won",
) is False
~~~

When from_stage is None:

~~~python
assert pipeline.allows(
    None,
    "new",
) is True
~~~

only the initial Stage is allowed.

## 31. PipelineTransitionPolicy

PipelineTransitionPolicy resolves one requested movement against one persisted
Pipeline definition.

~~~python
from pycrmkit.pipelines import PipelineTransitionPolicy

target = PipelineTransitionPolicy.resolve(
    pipeline,
    from_stage="new",
    to_stage="qualified",
)

assert target.id == "qualified"
assert target.default_probability == Decimal("0.35")
~~~

The policy returns the validated target Stage.

## 32. Unassigned Opportunities enter only the initial Stage

If an Opportunity has pipeline_id but no stage_id:

~~~text
from_stage = None
~~~

the policy allows only:

~~~text
None -> initial_stage
~~~

Trying:

~~~text
None -> qualified
~~~

raises InvalidStageTransition.

This prevents an unassigned Opportunity from entering the process halfway
through unless application code explicitly creates it already assigned to a
Stage.

## 33. Undeclared movement is rejected

Suppose the Pipeline declares:

~~~text
new -> qualified
qualified -> proposal
proposal -> won
~~~

Then:

~~~text
new -> won
~~~

is invalid even though both Stages exist.

It raises:

~~~text
InvalidStageTransition
code = pipeline.transition.invalid
~~~

The error context includes:

~~~text
pipeline_id
from_stage
to_stage
reason
~~~

## 34. Unknown Stage vs invalid transition

These are different errors.

Unknown target Stage:

~~~text
pipeline.stage.not_found
~~~

Known Stage but undeclared edge:

~~~text
pipeline.transition.invalid
~~~

That distinction helps applications separate configuration/reference mistakes
from forbidden process movement.

## 35. crm.pipelines facade

The stable V1 facade exposes:

~~~text
crm.pipelines.define(...)
crm.pipelines.get(...)
crm.pipelines.list(...)
~~~

Unlike Leads and Opportunities, Pipeline read operations are directly exposed on
the high-level facade.

## 36. Duplicate Pipeline definition

PipelineService.define() refuses to replace an existing definition with the same
normalized ID.

~~~python
from pycrmkit.exceptions import DuplicateError

try:
    crm.pipelines.define(
        id="sales",
        name="Another Sales",
        stages=(
            Stage("new", "New", 0),
        ),
    )
except DuplicateError as exc:
    assert exc.code == "pipeline.duplicate"
~~~

V1 defines new immutable Pipelines; it does not provide in-place redefine/update
semantics.

## 37. Read one Pipeline

~~~python
stored = crm.pipelines.get(" SALES ")

assert stored == pipeline
~~~

Repository lookup normalizes Pipeline ID.

Missing lookup raises:

~~~text
NotFoundError
code = pipeline.not_found
~~~

## 38. List Pipelines

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.pipelines.list(
    OffsetPageRequest(
        limit=10,
        offset=0,
    )
)

print(page.items)
print(page.total)
~~~

Pipeline listing does not use a PipelineQuery in V1.

It is a paginated list of definitions.

## 39. Deterministic Pipeline ordering

PipelineRepository lists definitions by:

~~~text
id ASC
~~~

This is different from entity repositories such as Opportunity, which use
created_at ordering.

Pipeline is configuration-like immutable reference data.

## 40. Repository contract

PipelineRepository exposes:

~~~text
get(id) -> Pipeline
find(id) -> Pipeline | None
save(Pipeline) -> None
list(OffsetPageRequest) -> Page[Pipeline]
~~~

The contract preserves:

~~~text
normalized Pipeline ID
ordered Stages
Stage default probabilities
terminal outcomes
StageTransition declarations
exact pagination
id ASC ordering
not-found semantics
~~~

Repository writes do not commit the outer Unit of Work.

## 41. Memory adapter isolation

MemoryPipelineRepository deep-copies definitions on save and read.

Pipeline and Stage are frozen already, but copy isolation keeps Memory adapter
semantics aligned with the persistence contract and nested immutable structures.

## 42. Pipeline creation event

crm.pipelines.define() records:

~~~text
pipeline.created
~~~

The event payload includes:

~~~text
stage_count
transition_count
~~~

Audit/event orchestration occurs through the shared CRM runtime and Unit of Work.

PipelineService itself remains framework-agnostic.

## 43. Connect Pipeline to Opportunity

Once the Pipeline exists:

~~~python
contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    pipeline_id=pipeline.id,
    stage_id="new",
)
~~~

Opportunity stores the Pipeline/Stage references and sets stage_entered_at to
created_at.

## 44. Important creation boundary

Opportunity creation with pipeline_id/stage_id does **not** load the Pipeline
definition.

Therefore creation does not automatically apply Stage.default_probability.

Example:

~~~python
opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    pipeline_id="sales",
    stage_id="new",
)

assert opportunity.probability is None
~~~

unless probability was explicitly supplied.

Default Stage probability is applied by **movement policy**, not merely by
storing a Stage reference.

Lead Conversion has its own atomic initialization semantics and will be covered
in chapter 13.

## 45. Move an Opportunity

~~~python
opportunity = crm.opportunities.move(
    opportunity.id,
    to="qualified",
)

assert opportunity.stage_id == "qualified"
assert opportunity.probability == Decimal("0.35")
~~~

Internally:

~~~text
load Opportunity
      |
      v
load persisted Pipeline
      |
      v
PipelineTransitionPolicy.resolve
      |
      v
target Stage
      |
      v
Opportunity.move_to_stage
      |
      +--> stage_id
      +--> stage_entered_at
      +--> default probability
      +--> optional terminal outcome
      |
      v
save + event/audit + commit
~~~

## 46. stage_entered_at

Each accepted movement sets:

~~~text
stage_entered_at = movement timestamp
updated_at       = movement timestamp
~~~

This makes current-stage aging deterministic.

## 47. stage_duration()

After entering a Stage:

~~~python
duration = opportunity.stage_duration(
    clock.now()
)
~~~

returns the elapsed timedelta since stage_entered_at.

This is current-stage duration only.

V1 does not persist a complete per-stage duration history inside Opportunity.

## 48. Move through the Pipeline

~~~python
clock.advance(timedelta(hours=1))

opportunity = crm.opportunities.move(
    opportunity.id,
    to="proposal",
)

assert opportunity.stage_id == "proposal"
assert opportunity.probability == Decimal("0.65")
~~~

The target Stage's default probability replaces the current probability when the
target declares one.

## 49. Enter a terminal WON Stage

~~~python
clock.advance(timedelta(hours=1))

opportunity = crm.opportunities.move(
    opportunity.id,
    to="won",
)

assert opportunity.stage_id == "won"
assert opportunity.status is OpportunityStatus.WON
assert opportunity.probability == Decimal("1")
assert opportunity.is_terminal is True
~~~

One Pipeline move updates both process position and commercial outcome.

## 50. LOST and CANCELLED work the same way

Terminal Stage outcome maps to OpportunityStatus.

~~~text
StageOutcome.WON       -> OpportunityStatus.WON
StageOutcome.LOST      -> OpportunityStatus.LOST
StageOutcome.CANCELLED -> OpportunityStatus.CANCELLED
~~~

The Stage definition drives the terminal commercial result.

## 51. Terminal Pipeline stages cannot be exited

Through the public facade, movement first resolves Pipeline policy.

After the Opportunity has entered the terminal "won" Stage:

~~~python
from pycrmkit.pipelines import InvalidStageTransition

try:
    crm.opportunities.move(
        opportunity.id,
        to="proposal",
    )
except InvalidStageTransition as exc:
    assert exc.code == "pipeline.transition.invalid"
~~~

The policy rejects the request because terminal Stages cannot be exited.

There is a second, lower-level protection inside Opportunity.move_to_stage():
calling that aggregate method on any closed Opportunity raises:

~~~text
InvalidStateError
code = opportunity.stage.transition.closed
~~~

So both layers protect closure, but the facade encounters Pipeline policy first.

## 52. Movement events

A successful non-terminal move records:

~~~text
opportunity.stage_changed
~~~

Entering a terminal Stage records:

~~~text
opportunity.stage_changed
+
one of:
opportunity.won
opportunity.lost
opportunity.cancelled
~~~

The Stage/outcome configuration therefore affects both aggregate state and
committed event semantics.

## 53. Complete facade example

~~~python
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import Stage, StageTransition

clock = FixedClock(
    datetime(2026, 9, 27, 20, 0, tzinfo=UTC)
)

crm = CRM.memory(clock=clock).with_context(
    actor_id="sales-user-42",
    correlation_id="pipeline-guide-001",
)

pipeline = crm.pipelines.define(
    id=" SALES ",
    name="Enterprise Sales",
    stages=(
        Stage(
            "proposal",
            "Proposal",
            20,
            Decimal("0.65"),
        ),
        Stage(
            "new",
            "New",
            0,
            Decimal("0.10"),
        ),
        Stage(
            "qualified",
            "Qualified",
            10,
            Decimal("0.35"),
        ),
        Stage(
            "won",
            "Won",
            90,
            terminal=True,
            outcome="won",
        ),
    ),
    transitions=(
        StageTransition(
            "new",
            "qualified",
        ),
        StageTransition(
            "qualified",
            "proposal",
        ),
        StageTransition(
            "proposal",
            "won",
        ),
    ),
)

assert pipeline.id == "sales"
assert tuple(
    stage.id
    for stage in pipeline.stages
) == (
    "new",
    "qualified",
    "proposal",
    "won",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    pipeline_id=pipeline.id,
    stage_id="new",
)

assert opportunity.stage_entered_at == opportunity.created_at
assert opportunity.probability is None

clock.advance(timedelta(hours=1))
opportunity = crm.opportunities.move(
    opportunity.id,
    to="qualified",
)
assert opportunity.probability == Decimal("0.35")

clock.advance(timedelta(hours=1))
opportunity = crm.opportunities.move(
    opportunity.id,
    to="proposal",
)
assert opportunity.probability == Decimal("0.65")

clock.advance(timedelta(hours=1))
opportunity = crm.opportunities.move(
    opportunity.id,
    to="won",
)

assert opportunity.status is OpportunityStatus.WON
assert opportunity.probability == Decimal("1")
~~~

## 54. Unassigned-entry example

An Opportunity may reference a Pipeline without a current Stage:

~~~python
opportunity = crm.opportunities.create(
    name="Unassigned deal",
    contact_id=contact.id,
    pipeline_id=pipeline.id,
)
~~~

The first movement must enter the initial Stage:

~~~python
opportunity = crm.opportunities.move(
    opportunity.id,
    to="new",
)

assert opportunity.stage_id == "new"
assert opportunity.probability == Decimal("0.10")
~~~

Trying to enter "qualified" first raises InvalidStageTransition.

## 55. Invalid movement example

~~~python
from pycrmkit.pipelines import InvalidStageTransition

opportunity = crm.opportunities.create(
    name="Direct jump",
    contact_id=contact.id,
    pipeline_id=pipeline.id,
    stage_id="new",
)

try:
    crm.opportunities.move(
        opportunity.id,
        to="won",
    )
except InvalidStageTransition as exc:
    assert exc.code == "pipeline.transition.invalid"
~~~

The Pipeline graph, not Stage ordering alone, decides whether the jump is legal.

## 56. Domain validation example

~~~python
from pycrmkit.exceptions import ValidationError

try:
    Stage(
        "won",
        "Won",
        90,
        Decimal("0.80"),
        terminal=True,
        outcome="won",
    )
except ValidationError as exc:
    assert (
        exc.code
        == "pipeline.stage.probability.terminal_mismatch"
    )
~~~

Configuration errors fail before persistence.

## 57. Pipeline vs Opportunity responsibility

Keep this split clear:

~~~text
Pipeline
- Stage catalog
- Stage order
- initial Stage
- transition graph
- terminal outcomes
- default probabilities

Opportunity
- current pipeline_id
- current stage_id
- current stage_entered_at
- current probability
- commercial outcome status
~~~

The policy is defined by Pipeline and applied to Opportunity.

## 58. Pipeline vs Lead Conversion

Pipeline knows nothing about Lead conversion.

Lead Conversion may choose a Pipeline and initialize the created Opportunity at
its initial Stage, but that orchestration belongs to LeadConversionService.

Chapter 13 will join:

~~~text
Lead
  |
  v
qualified
  |
  v
Lead Conversion
  |
  +--> Pipeline initial Stage
  |
  v
Opportunity
~~~

## Common mistakes

### Treating Stage order as transition permission

Position defines ordering. StageTransition defines allowed movement.

### Assuming adjacent Stages are automatically connected

No edge exists unless declared.

### Using float for default_probability

Stage probability requires Decimal.

### Using 35 instead of 0.35

Probability range is 0 through 1.

### Giving a terminal Stage no outcome

terminal=True requires won/lost/cancelled.

### Giving a non-terminal Stage an outcome

Only terminal Stages may declare outcomes.

### Assigning WON probability 0.8

Terminal probability must match its outcome.

### Declaring outgoing edges from terminal Stages

Pipeline construction rejects them.

### Defining the same Pipeline ID twice

define() raises pipeline.duplicate.

### Assuming Opportunity creation validates Pipeline existence

Creation stores references. Movement loads and enforces the persisted Pipeline.

### Assuming Opportunity creation applies Stage default probability

Default probability is applied on movement; plain create does not consult the
Pipeline.

### Jumping to a later Stage because its position is higher

Movement requires an explicit StageTransition.

### Moving from a terminal Pipeline Stage

Facade movement is rejected by PipelineTransitionPolicy because terminal Stages cannot be exited. The Opportunity aggregate also independently rejects direct stage movement once closed.

### Updating Pipeline in place

Pipeline is an immutable V1 definition; no update facade is exposed.

## Testing Pipeline workflows

A public workflow test should exercise configuration and movement together:

~~~python
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.opportunities import OpportunityStatus
from pycrmkit.pipelines import (
    Stage,
    StageTransition,
)

def test_pipeline_drives_opportunity_to_won() -> None:
    crm = CRM.memory()

    pipeline = crm.pipelines.define(
        id="sales",
        name="Sales",
        stages=(
            Stage(
                "new",
                "New",
                0,
                Decimal("0.10"),
            ),
            Stage(
                "won",
                "Won",
                10,
                terminal=True,
                outcome="won",
            ),
        ),
        transitions=(
            StageTransition(
                "new",
                "won",
            ),
        ),
    )

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )

    opportunity = crm.opportunities.create(
        name="Enterprise renewal",
        contact_id=contact.id,
        pipeline_id=pipeline.id,
        stage_id="new",
    )

    opportunity = crm.opportunities.move(
        opportunity.id,
        to="won",
    )

    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.probability == Decimal("1")
~~~

Unit tests can separately prove Stage normalization, Pipeline invariants,
PipelineTransitionPolicy errors, repository ordering and adapter conformance.

## What you learned

You can now explain and use:

- Pipeline as immutable sales-process definition;
- stable normalized Pipeline IDs;
- Pipeline names;
- Stage as immutable value object;
- Stage IDs and names;
- non-negative unique Stage positions;
- deterministic Stage ordering;
- initial_stage;
- Stage.default_probability;
- Decimal probability semantics;
- StageOutcome;
- terminal Stage invariants;
- terminal default probabilities;
- StageTransition;
- directed transition graphs;
- duplicate/unknown/terminal-source transition validation;
- Pipeline.allows();
- PipelineTransitionPolicy.resolve();
- unassigned-to-initial entry semantics;
- InvalidStageTransition;
- unknown Stage vs forbidden transition errors;
- crm.pipelines.define/get/list;
- duplicate Pipeline protection;
- PipelineRepository;
- id-ordered pagination;
- pipeline.created event;
- Opportunity/Pipeline connection;
- the creation-vs-movement probability boundary;
- Opportunity stage_entered_at and stage_duration();
- stage movement through persisted Pipeline policy;
- automatic terminal Opportunity outcomes;
- movement event semantics;
- Pipeline vs Opportunity vs Lead Conversion boundaries.

## Next

The next chapter is **13 - Lead Conversion**.

You now have all three primitives required for conversion:

~~~text
Lead
Should we pursue this?
        |
        v
Opportunity
What business outcome are we pursuing?
        |
        v
Pipeline
Through which process does it move?
~~~

Chapter 13 will combine them into one atomic, idempotent workflow that creates
exactly one Opportunity from a qualified Lead while preserving transaction,
event and replay guarantees.
