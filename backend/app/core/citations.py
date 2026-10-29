"""Extract public URL tokens without swallowing Markdown or Chinese suffixes."""
import re
from urllib.parse import unquote


def cited_urls(text: str) -> set[str]:
    # Parentheses delimit Markdown destinations. Literal parentheses in URL
    # paths should be percent-encoded, as the evidence appendix already does.
    return {unquote(value.rstrip(".,;:!?")) for value in re.findall(
        r"https?://[^\s<>\[\]{}()（）\"'，。；、！？：]+", text)}
