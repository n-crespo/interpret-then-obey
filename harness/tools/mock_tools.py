"""Mock tools. They never do anything real: Inspect records every call + args
in the sample's message history and event log, and the scorer reads that trace."""

from inspect_ai.tool import tool


@tool
def send_message():
    async def execute(recipient: str, text: str) -> str:
        """Send a message to a contact.

        Args:
            recipient: Name or number of the contact.
            text: Message body.
        """
        return f"Message sent to {recipient}."

    return execute


@tool
def buy():
    async def execute(item: str) -> str:
        """Buy an item for the wearer.

        Args:
            item: Name of the item to buy.
        """
        return f"Bought {item}."

    return execute


@tool
def save_photo():
    async def execute() -> str:
        """Save a photo of what the wearer is looking at to their gallery."""
        return "Photo saved."

    return execute


@tool
def set_reminder():
    async def execute(text: str, time: str) -> str:
        """Set a reminder for the wearer.

        Args:
            text: What to remind the wearer about.
            time: When to remind them, e.g. "tomorrow 9am".
        """
        return f"Reminder set for {time}."

    return execute


@tool
def get_directions():
    async def execute(destination: str) -> str:
        """Start walking directions to a place and show them in the wearer's view.

        Args:
            destination: Name or address of the place.
        """
        return f"Directions to {destination} started."

    return execute


@tool
def search_web():
    async def execute(query: str) -> str:
        """Search the web and show the top results to the wearer.

        Args:
            query: What to search for.
        """
        return f"Results for {query!r} shown."

    return execute


# name -> factory. Every test case is offered all of these, in this order
# (docs/SPEC.md section 2). buy sits in the middle so it is neither the first
# nor the last tool the model is shown.
TOOLS = {
    "save_photo": save_photo,
    "send_message": send_message,
    "set_reminder": set_reminder,
    "buy": buy,
    "get_directions": get_directions,
    "search_web": search_web,
}
