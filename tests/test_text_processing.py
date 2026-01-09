"""Tests for text processing utilities (tokenization, stemming)."""

import pytest

from messages.text_processing import (
    STEMMER_AVAILABLE,
    STOP_WORDS,
    get_stemmer_info,
    process_query_for_search,
    process_text_for_index,
    remove_stop_words,
    stem_tokens,
    stem_word,
    tokenize,
)


class TestTokenize:
    """Tests for tokenize function."""

    def test_tokenize_basic(self):
        """Should split text into lowercase tokens."""
        tokens = tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_tokenize_with_punctuation(self):
        """Should handle punctuation."""
        tokens = tokenize("Hello, World! How are you?")
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_tokenize_preserves_contractions(self):
        """Should preserve contractions as single tokens."""
        tokens = tokenize("I'm can't won't")
        assert "i'm" in tokens
        assert "can't" in tokens

    def test_tokenize_empty_string(self):
        """Should return empty list for empty string."""
        tokens = tokenize("")
        assert tokens == []

    def test_tokenize_none(self):
        """Should handle None input."""
        tokens = tokenize(None)
        assert tokens == []

    def test_tokenize_with_numbers(self):
        """Should include numbers as tokens."""
        tokens = tokenize("Call me at 555-1234")
        assert "555" in tokens
        assert "1234" in tokens


class TestStopWords:
    """Tests for stop word removal."""

    def test_remove_stop_words(self):
        """Should remove common stop words."""
        tokens = ["the", "quick", "brown", "fox"]
        result = remove_stop_words(tokens)
        assert "the" not in result
        assert "quick" in result
        assert "brown" in result

    def test_stop_words_includes_common_words(self):
        """STOP_WORDS should include common English words."""
        assert "the" in STOP_WORDS
        assert "a" in STOP_WORDS
        assert "is" in STOP_WORDS
        assert "and" in STOP_WORDS
        assert "or" in STOP_WORDS


@pytest.mark.skipif(not STEMMER_AVAILABLE, reason="Stemmer not installed")
class TestStemming:
    """Tests for stemming functions (requires snowballstemmer)."""

    def test_stem_word_basic(self):
        """Should stem words to their root form."""
        assert stem_word("running") == "run"
        assert stem_word("runs") == "run"
        assert stem_word("runner") == "runner"  # Different root

    def test_stem_word_plurals(self):
        """Should handle plural forms."""
        assert stem_word("dogs") == "dog"
        assert stem_word("cats") == "cat"
        assert stem_word("babies") == "babi"

    def test_stem_word_past_tense(self):
        """Should handle past tense."""
        assert stem_word("walked") == "walk"
        assert stem_word("played") == "play"

    def test_stem_word_ing_forms(self):
        """Should handle -ing forms."""
        assert stem_word("walking") == "walk"
        assert stem_word("playing") == "play"
        assert stem_word("thinking") == "think"

    def test_stem_tokens_list(self):
        """Should stem a list of tokens."""
        tokens = ["running", "dogs", "played"]
        stemmed = stem_tokens(tokens)
        assert stemmed == ["run", "dog", "play"]

    def test_stem_empty_word(self):
        """Should handle empty string."""
        assert stem_word("") == ""


@pytest.mark.skipif(not STEMMER_AVAILABLE, reason="Stemmer not installed")
class TestProcessTextForIndex:
    """Tests for process_text_for_index function."""

    def test_process_text_basic(self):
        """Should tokenize and stem text."""
        result = process_text_for_index("The dogs are running")
        # Should be stemmed and lowercased
        assert "dog" in result
        assert "run" in result

    def test_process_text_with_stop_word_removal(self):
        """Should optionally remove stop words."""
        result = process_text_for_index("The dogs are running", remove_stops=True)
        assert "the" not in result.split()
        assert "are" not in result.split()
        assert "dog" in result
        assert "run" in result

    def test_process_text_empty(self):
        """Should handle empty string."""
        assert process_text_for_index("") == ""


@pytest.mark.skipif(not STEMMER_AVAILABLE, reason="Stemmer not installed")
class TestProcessQueryForSearch:
    """Tests for process_query_for_search function."""

    def test_process_query_basic(self):
        """Should stem query words."""
        result = process_query_for_search("running dogs")
        assert "run" in result
        assert "dog" in result

    def test_process_query_preserves_operators(self):
        """Should preserve FTS5 operators."""
        result = process_query_for_search("running AND playing")
        assert "AND" in result
        result = process_query_for_search("dogs OR cats")
        assert "OR" in result

    def test_process_query_handles_phrases(self):
        """Should stem words inside quoted phrases."""
        result = process_query_for_search('"running dogs"')
        assert '"' in result
        assert "run" in result
        assert "dog" in result

    def test_process_query_empty(self):
        """Should handle empty string."""
        assert process_query_for_search("") == ""


class TestStemmerInfo:
    """Tests for get_stemmer_info function."""

    def test_stemmer_info_structure(self):
        """Should return dictionary with expected keys."""
        info = get_stemmer_info()
        assert "available" in info
        assert "algorithm" in info
        assert "stop_words_count" in info
        assert info["stop_words_count"] > 0

    @pytest.mark.skipif(not STEMMER_AVAILABLE, reason="Stemmer not installed")
    def test_stemmer_info_available(self):
        """Should indicate stemmer is available when installed."""
        info = get_stemmer_info()
        assert info["available"] is True
        assert info["algorithm"] is not None
