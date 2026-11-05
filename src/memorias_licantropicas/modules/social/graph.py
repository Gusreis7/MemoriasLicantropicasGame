"""Ciclo entre agentes sociais; reservas e persistência continuam no domínio."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph


class SocialCycleState(TypedDict, total=False):
    game_id: UUID
    route: Literal["advance", "extract", "schedule", "done"]
    case: Any
    game: Any
    world: Any
    social: Any
    encounter: Any
    result: bool
    nodes: tuple[str, ...]


CycleNode = Callable[[SocialCycleState], Awaitable[dict]]


def build_social_cycle(
    *,
    prepare: CycleNode,
    advance: CycleNode,
    extract: CycleNode,
    revalidate: CycleNode,
    schedule: CycleNode,
):
    """Uma invocação por partida/tick, sem checkpointer ou estado compartilhado."""
    graph = StateGraph(SocialCycleState)
    for name, node in {
        "prepare": prepare,
        "advance_encounter": advance,
        "extract_knowledge": extract,
        "revalidate_world": revalidate,
        "schedule_encounter": schedule,
    }.items():
        graph.add_node(name, node)
    graph.add_edge(START, "prepare")
    graph.add_conditional_edges(
        "prepare",
        lambda state: state["route"],
        {
            "advance": "advance_encounter",
            "extract": "extract_knowledge",
            "done": END,
        },
    )
    graph.add_edge("advance_encounter", END)
    graph.add_edge("extract_knowledge", "revalidate_world")
    graph.add_conditional_edges(
        "revalidate_world",
        lambda state: state["route"],
        {
            "schedule": "schedule_encounter",
            "done": END,
        },
    )
    graph.add_edge("schedule_encounter", END)
    return graph.compile()
