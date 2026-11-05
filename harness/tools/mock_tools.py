"""Mock tools. They never do anything real: Inspect records every call + args
in the sample's message history and event log, and the scorer reads that trace."""

from inspect_ai.tool import tool


@tool
def add_to_cart():
    async def execute(item: str, quantity: int = 1) -> str:
        """Add an item to the wearer's shopping cart.

        Args:
            item: Name of the item to add.
            quantity: How many to add.
        """
        return f"Added {quantity} x {item} to cart."

    return execute


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
def save_note():
    async def execute(text: str) -> str:
        """Save a note for the wearer.

        Args:
            text: Note content.
        """
        return "Note saved."

    return execute


# name -> factory. Manifest rows may list a subset in "tools"; default is all.
TOOLS = {"add_to_cart": add_to_cart, "send_message": send_message, "save_note": save_note}