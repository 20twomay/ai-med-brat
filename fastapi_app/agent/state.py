from typing import Annotated, Optional, TypedDict

from langchain.messages import AnyMessage
from langgraph.graph import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    iteration: int
    max_iterations: int
    charts: list[str]
    is_request_valid: bool
    needs_clarification: bool
