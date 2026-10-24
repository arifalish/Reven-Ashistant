import re

# AI words to strip out based on common ChatGPT fingerprints
AI_WORDS_TO_STRIP = [
    "delve", "testament", "tapestry", "in conclusion", "to summarize",
    "it is important to note", "moreover", "furthermore", "realm"
]

ZERO_WIDTH_CHARS = [
    "\u200b", "\u200c", "\u200d", "\ufeff"
]

def remove_zero_width_chars(text: str) -> str:
    for char in ZERO_WIDTH_CHARS:
        text = text.replace(char, "")
    return text

def remove_ai_words(text: str) -> str:
    # Case-insensitive replacement for AI words
    for word in AI_WORDS_TO_STRIP:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        text = pattern.sub("", text)

    # Simple rule of three triad mitigation (e.g., removing repeating structures)
    # This is a basic mock implementation.
    text = re.sub(r'(\b\w+\b), \1, and \1', r'\1', text, flags=re.IGNORECASE)

    # Cleanup extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def clean_and_humanize(text: str) -> str:
    """
    Mandatory node before finalizing any text output.
    """
    if not text:
        return text

    text = remove_zero_width_chars(text)
    text = remove_ai_words(text)

    return text
