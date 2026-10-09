import re
from dataclasses import dataclass

BANNED_WORDS = ("guaranteed", "act now", "click here")
HASHTAG_RE = re.compile(r"#\w+")


@dataclass(frozen=True)
class Profile:
    max_length: int
    max_hashtags: int
    max_exclamations: int
    caps_min_len: int  # ALL-CAPS words this long or longer are rejected
    banned_words: tuple = ()


PROFILES = {
    "x": Profile(280, 2, 1, 5, BANNED_WORDS),
    "linkedin": Profile(2000, 5, 1, 2, BANNED_WORDS),
    "telegram": Profile(4096, 3, 3, 5),
}


def validate_variant(platform: str, text: str) -> list[str]:
    """Return a list of broken rules. An empty list means the variant is valid."""
    profile = PROFILES.get(platform)
    if profile is None:
        raise ValueError(f"Unknown platform: {platform}")

    errors = []

    if len(text) > profile.max_length:
        errors.append(
            f"length: {len(text)} characters exceeds the {platform} "
            f"limit of {profile.max_length}"
        )

    hashtags = HASHTAG_RE.findall(text)
    if len(hashtags) > profile.max_hashtags:
        errors.append(
            f"hashtags: {len(hashtags)} hashtags exceeds the {platform} "
            f"limit of {profile.max_hashtags}"
        )

    exclamations = text.count("!")
    if exclamations > profile.max_exclamations:
        errors.append(
            f"tone: {exclamations} exclamation marks exceeds the {platform} "
            f"limit of {profile.max_exclamations}"
        )

    prose = HASHTAG_RE.sub("", text)  # ignore hashtags like #AI
    caps = re.findall(r"\b[A-Z]{%d,}\b" % profile.caps_min_len, prose)
    if caps:
        errors.append(
            f"tone: ALL-CAPS words not allowed on {platform}: {', '.join(caps)}"
        )

    lowered = text.lower()
    for word in profile.banned_words:
        if word in lowered:
            errors.append(f"tone: banned phrase on {platform}: '{word}'")

    return errors