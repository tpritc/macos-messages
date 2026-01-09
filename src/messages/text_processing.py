"""Text processing utilities for search.

This module provides text processing functions including:
- Tokenization
- Stemming (using Snowball/Porter stemmer)
- Stop word removal

These are used to enhance search accuracy by matching word stems rather
than exact words (e.g., "running" matches "run", "runner", "runs").
"""

import re
from typing import Optional

# Try to import snowballstemmer, fall back gracefully if not available
try:
    import snowballstemmer

    _stemmer = snowballstemmer.stemmer("english")
    STEMMER_AVAILABLE = True
except ImportError:
    _stemmer = None
    STEMMER_AVAILABLE = False


# Common English stop words that don't add much search value
STOP_WORDS = frozenset([
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "he", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "to", "was", "were", "will", "with", "you", "your",
    "i", "me", "my", "we", "our", "they", "them", "their",
    "this", "these", "those", "what", "which", "who", "whom",
    "can", "could", "do", "does", "did", "have", "had", "having",
    "would", "should", "may", "might", "must", "shall",
    "am", "been", "being", "so", "but", "if", "then", "than",
    "just", "very", "too", "also", "only", "now", "here", "there",
])


def tokenize(text: str) -> list[str]:
    """Tokenize text into words.

    Splits on non-alphanumeric characters and converts to lowercase.
    Preserves contractions as single tokens.

    Args:
        text: Input text to tokenize

    Returns:
        List of lowercase word tokens
    """
    if not text:
        return []

    # Convert to lowercase and split on word boundaries
    # Keep apostrophes within words for contractions
    tokens = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())

    return tokens


def remove_stop_words(tokens: list[str]) -> list[str]:
    """Remove common stop words from token list.

    Args:
        tokens: List of word tokens

    Returns:
        List with stop words removed
    """
    return [t for t in tokens if t not in STOP_WORDS]


def stem_word(word: str) -> str:
    """Stem a single word using Snowball stemmer.

    Args:
        word: Word to stem (should be lowercase)

    Returns:
        Stemmed word, or original if stemmer not available
    """
    if not STEMMER_AVAILABLE or not word:
        return word

    return _stemmer.stemWord(word)


def stem_tokens(tokens: list[str]) -> list[str]:
    """Stem a list of tokens.

    Args:
        tokens: List of word tokens

    Returns:
        List of stemmed tokens
    """
    if not STEMMER_AVAILABLE:
        return tokens

    return _stemmer.stemWords(tokens)


def process_text_for_index(text: str, remove_stops: bool = False) -> str:
    """Process text for indexing with stemming.

    Tokenizes, optionally removes stop words, stems, and rejoins.

    Args:
        text: Raw text to process
        remove_stops: Whether to remove stop words (default False)

    Returns:
        Processed text with stemmed words
    """
    if not text:
        return ""

    tokens = tokenize(text)

    if remove_stops:
        tokens = remove_stop_words(tokens)

    if STEMMER_AVAILABLE:
        tokens = stem_tokens(tokens)

    return " ".join(tokens)


def process_query_for_search(query: str) -> str:
    """Process a search query for stemmed searching.

    Handles FTS5 operators (AND, OR, NOT, quotes) while stemming words.

    Args:
        query: Raw search query

    Returns:
        Processed query with stemmed words
    """
    if not query:
        return ""

    if not STEMMER_AVAILABLE:
        return query

    # Handle quoted phrases specially - stem words inside quotes
    # but preserve the phrase structure
    result_parts = []
    i = 0
    chars = query

    while i < len(chars):
        # Handle quoted phrases
        if chars[i] == '"':
            end_quote = chars.find('"', i + 1)
            if end_quote != -1:
                phrase = chars[i + 1:end_quote]
                # Stem words in the phrase but keep it as a phrase
                stemmed_phrase = process_text_for_index(phrase)
                result_parts.append(f'"{stemmed_phrase}"')
                i = end_quote + 1
                continue
            else:
                # Unclosed quote, treat rest as phrase
                phrase = chars[i + 1:]
                stemmed_phrase = process_text_for_index(phrase)
                result_parts.append(f'"{stemmed_phrase}"')
                break

        # Handle FTS5 operators (keep them as-is)
        for op in ["AND", "OR", "NOT", "NEAR"]:
            if chars[i:i + len(op)].upper() == op and (
                i == 0 or not chars[i - 1].isalnum()
            ) and (
                i + len(op) >= len(chars) or not chars[i + len(op)].isalnum()
            ):
                result_parts.append(op)
                i += len(op)
                break
        else:
            # Handle regular words
            match = re.match(r"[a-zA-Z0-9]+(?:'[a-zA-Z]+)?", chars[i:])
            if match:
                word = match.group().lower()
                stemmed = stem_word(word)
                result_parts.append(stemmed)
                i += len(match.group())
            elif chars[i].isspace():
                result_parts.append(" ")
                i += 1
            else:
                # Keep other characters (parentheses, etc.)
                result_parts.append(chars[i])
                i += 1

    # Clean up extra spaces
    result = "".join(result_parts)
    result = re.sub(r"\s+", " ", result).strip()

    return result


def get_stemmer_info() -> dict:
    """Get information about the stemmer configuration.

    Returns:
        Dictionary with stemmer availability and configuration
    """
    return {
        "available": STEMMER_AVAILABLE,
        "algorithm": "snowball/english" if STEMMER_AVAILABLE else None,
        "stop_words_count": len(STOP_WORDS),
    }
