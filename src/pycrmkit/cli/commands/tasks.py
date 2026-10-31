"""Tasks and action items management commands for PyCRMKit CLI."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from pycrmkit.cli.console import console
from pycrmkit.cli.exit_codes import ExitCode
from pycrmkit.cli.state import get_crm_context
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import NotFoundError, ValidationError
from pycrmkit.tasks import TaskId, TaskPriority, TaskQuery, TaskStatus

tasks_app = typer.Typer(
    name="tasks",
    help="Manage tasks, scheduled follow-ups, and action items.",
    no_args_is_help=True,
)


def _resolve_task_id(crm, prefix_or_id: str) -> TaskId:
    """Resolve a task ID from full UUID or prefix."""
    clean = prefix_or_id.strip().rstrip(".")
    if len(clean) == 36 and "-" in clean:
        try:
            return TaskId(clean)
        except (ValueError, TypeError):
            pass

    page = crm.tasks.list(page=OffsetPageRequest(limit=100))
    for t in page.items:
        if str(t.id).startswith(clean):
            return t.id

    raise NotFoundError(f"Task with ID prefix '{prefix_or_id}' not found.")


@tasks_app.command("list")
def list_tasks(
    status_filter: Annotated[
        str | None,
        typer.Option(
            "--status", "-s", help="Filter by status (open, in_progress, completed, cancelled)"
        ),
    ] = None,
    priority_filter: Annotated[
        str | None,
        typer.Option("--priority", "-p", help="Filter by priority (low, normal, high, urgent)"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", "-l", help="Number of tasks to return")] = 20,
    offset: Annotated[int, typer.Option("--offset", "-o", help="Offset for pagination")] = 0,
) -> None:
    """List operational tasks, due dates, urgency, and statuses."""
    query = TaskQuery()
    if status_filter:
        try:
            query = query.with_status(TaskStatus(status_filter.lower()))
        except ValueError:
            console.print(
                f"[bold red]Unknown status:[/bold red] '{status_filter}'. Allowed: open, in_progress, completed, cancelled."
            )
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from None

    if priority_filter:
        try:
            prio = TaskPriority[priority_filter.upper()]
            query = query.with_priority(prio)
        except KeyError:
            console.print(
                f"[bold red]Unknown priority:[/bold red] '{priority_filter}'. Allowed: low, normal, high, urgent."
            )
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from None

    with get_crm_context(save=False) as crm:
        page = crm.tasks.list(query=query, page=OffsetPageRequest(limit=limit, offset=offset))

    if not page.items:
        console.print(
            "[yellow]No tasks found matching criteria. Use 'pck tasks create' or 'pck seed' to add tasks.[/yellow]"
        )
        return

    table = Table(title=f"Action Items & Tasks ({page.total} total)", border_style="dim")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Title", style="white")
    table.add_column("Priority", justify="center")
    table.add_column("Due Date", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Linked To", style="dim")

    for task in page.items:
        due_str = task.due_at.strftime("%Y-%m-%d") if task.due_at else "-"
        prio_style = {
            TaskPriority.LOW: "[dim]LOW[/dim]",
            TaskPriority.NORMAL: "[white]NORMAL[/white]",
            TaskPriority.HIGH: "[yellow]HIGH[/yellow]",
            TaskPriority.URGENT: "[bold red]URGENT[/bold red]",
        }.get(task.priority, str(task.priority.name))

        status_style = {
            TaskStatus.OPEN: "[cyan]OPEN[/cyan]",
            TaskStatus.IN_PROGRESS: "[blue]IN PROGRESS[/blue]",
            TaskStatus.COMPLETED: "[bold green]COMPLETED[/bold green]",
            TaskStatus.CANCELLED: "[dim red]CANCELLED[/dim red]",
        }.get(task.status, str(task.status.value))

        links = ", ".join(f"{ref.kind}:{str(ref.id)[:6]}" for ref in task.references) or "-"

        table.add_row(
            str(task.id)[:8] + "...",
            task.title,
            prio_style,
            due_str,
            status_style,
            links,
        )

    console.print(table)


@tasks_app.command("create")
def create_task(
    title: Annotated[str, typer.Argument(help="Task objective / action item")],
    due: Annotated[
        str | None, typer.Option("--due", "-d", help="Due date in YYYY-MM-DD format")
    ] = None,
    priority: Annotated[
        str, typer.Option("--priority", "-p", help="Urgency: low, normal, high, urgent")
    ] = "normal",
    description: Annotated[str | None, typer.Option("--desc", help="Detailed action notes")] = None,
) -> None:
    """Create a new action item or follow-up task."""
    due_at = None
    if due:
        try:
            parsed_date = datetime.strptime(due, "%Y-%m-%d").replace(tzinfo=UTC)
            due_at = parsed_date
        except ValueError as exc:
            console.print(
                f"[bold red]Invalid date format:[/bold red] '{due}'. Expected YYYY-MM-DD."
            )
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc

    with get_crm_context(save=True) as crm:
        try:
            task = crm.tasks.create(
                title=title,
                due_at=due_at,
                priority=priority.lower(),
                description=description,
            )
        except (ValidationError, ValueError) as exc:
            console.print(f"[bold red]Validation error:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.VALIDATION_ERROR)) from exc
        except Exception as exc:
            console.print(f"[bold red]Failed to create task:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc

    console.print(
        Panel(
            f"[bold green]✓ Task Created[/bold green]\n\n"
            f"[bold]ID:[/bold] {task.id}\n"
            f"[bold]Title:[/bold] {task.title}\n"
            f"[bold]Priority:[/bold] {task.priority.name}\n"
            f"[bold]Due:[/bold] {due or '<none>'}",
            border_style="green",
        )
    )


@tasks_app.command("complete")
def complete_task(
    task_id: Annotated[str, typer.Argument(help="Task UUID or prefix")],
) -> None:
    """Mark a pending task as completed."""
    with get_crm_context(save=True) as crm:
        try:
            tid = _resolve_task_id(crm, task_id)
            task = crm.tasks.complete(tid)
        except NotFoundError as exc:
            console.print(f"[bold red]Not found:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc
        except Exception as exc:
            console.print(f"[bold red]Failed to complete task:[/bold red] {exc}")
            raise typer.Exit(code=int(ExitCode.GENERAL_ERROR)) from exc

    console.print(
        Panel(
            f"[bold green]✓ Task Marked as Completed[/bold green]\n\n"
            f"[bold]ID:[/bold] {task.id}\n"
            f"[bold]Title:[/bold] {task.title}\n"
            f"[bold]Status:[/bold] [bold green]COMPLETED[/bold green]",
            border_style="green",
        )
    )
