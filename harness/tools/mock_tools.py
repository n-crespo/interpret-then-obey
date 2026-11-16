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
def translate_text():
    async def execute(text: str, target_language: str) -> str:
        """Translate text the wearer is looking at and show the translation.

        Args:
            text: The text to translate.
            target_language: Language to translate into.
        """
        return f"Translation into {target_language} shown."

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


# name -> factory. Manifest rows may list a subset in "tools"; default is all.
TOOLS = {
    "add_to_cart": add_to_cart,
    "buy": buy,
    "send_message": send_message,
    "save_note": save_note,
    "save_photo": save_photo,
    "set_reminder": set_reminder,
    "get_directions": get_directions,
    "translate_text": translate_text,
    "search_web": search_web,
}
