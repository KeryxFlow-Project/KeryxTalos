"""Tests for help modal and glossary widgets - logic tests only."""


from keryxflow.core.glossary import GLOSSARY, get_term, search_glossary
from keryxflow.hermes.widgets.help import (
    GlossaryBrowser,
    HelpModal,
    QuickHelpWidget,
)


class TestHelpModal:
    """Tests for HelpModal initialization and logic."""

    def test_init_no_term(self):
        """Test HelpModal without specific term."""
        modal = HelpModal()
        assert modal._term is None
        assert modal._show_detailed is True

    def test_init_with_term(self):
        """Test HelpModal with specific term."""
        modal = HelpModal(term="rsi")
        assert modal._term == "rsi"
        assert modal._show_detailed is True

    def test_init_without_detailed(self):
        """Test HelpModal without detailed view."""
        modal = HelpModal(term="rsi", show_detailed=False)
        assert modal._term == "rsi"
        assert modal._show_detailed is False

    def test_search_results_init(self):
        """Test search results list initialization."""
        modal = HelpModal()
        assert modal._search_results == []


class TestQuickHelpWidget:
    """Tests for QuickHelpWidget logic."""

    def test_init(self):
        """Test QuickHelpWidget initialization."""
        widget = QuickHelpWidget()
        assert widget._current_term is None

    def test_current_term_storage(self):
        """Test storing current term."""
        widget = QuickHelpWidget()
        widget._current_term = "rsi"
        assert widget._current_term == "rsi"

    def test_term_can_be_cleared(self):
        """Test term can be set to None."""
        widget = QuickHelpWidget()
        widget._current_term = "rsi"
        widget._current_term = None
        assert widget._current_term is None


class TestGlossaryBrowser:
    """Tests for GlossaryBrowser logic."""

    def test_init_defaults(self):
        """Test GlossaryBrowser initializes with defaults."""
        browser = GlossaryBrowser()
        assert browser._current_category == "basics"

    def test_current_category_storage(self):
        """Test category storage."""
        browser = GlossaryBrowser()

        browser._current_category = "indicators"
        assert browser._current_category == "indicators"

        browser._current_category = "risk"
        assert browser._current_category == "risk"


class TestGlossaryIntegration:
    """Integration tests with glossary module."""

    def test_all_categories_have_terms(self):
        """Test all categories have at least one term."""
        categories = ["basics", "indicators", "risk", "orders", "analysis"]

        for category in categories:
            terms = [e for e in GLOSSARY.values() if e.category == category]
            assert len(terms) > 0, f"Category '{category}' has no terms"

    def test_common_terms_exist(self):
        """Test common terms exist in glossary."""
        common_terms = [
            "rsi",
            "macd",
            "stop_loss",
            "position",
            "pnl",
            "bullish",
            "bearish",
        ]

        for term in common_terms:
            entry = get_term(term)
            assert entry is not None, f"Term '{term}' not found in glossary"

    def test_search_returns_results(self):
        """Test search returns relevant results."""
        results = search_glossary("stop")
        assert len(results) > 0
        assert any("stop" in r.name.lower() for r in results)

    def test_search_case_insensitive(self):
        """Test search is case insensitive."""
        results_lower = search_glossary("rsi")
        results_upper = search_glossary("RSI")

        assert len(results_lower) == len(results_upper)

    def test_term_has_all_fields(self):
        """Test all glossary entries have required fields."""
        for term, entry in GLOSSARY.items():
            assert entry.term, f"Term '{term}' missing 'term' field"
            assert entry.name, f"Term '{term}' missing 'name' field"
            assert entry.simple, f"Term '{term}' missing 'simple' field"
            assert entry.technical, f"Term '{term}' missing 'technical' field"
            assert entry.why_matters, f"Term '{term}' missing 'why_matters' field"
            assert entry.category, f"Term '{term}' missing 'category' field"

    def test_glossary_categories_valid(self):
        """Test all entries have valid categories."""
        valid_categories = {"basics", "indicators", "risk", "orders", "analysis"}

        for term, entry in GLOSSARY.items():
            assert (
                entry.category in valid_categories
            ), f"Term '{term}' has invalid category '{entry.category}'"

    def test_search_empty_query(self):
        """Test search with empty-ish query returns nothing."""
        results = search_glossary("x")  # Single char, unlikely match
        # Just ensure it doesn't crash and returns a list
        assert isinstance(results, list)

    def test_get_term_not_found(self):
        """Test get_term returns None for unknown term."""
        result = get_term("nonexistent_term_xyz")
        assert result is None

    def test_get_term_case_insensitive(self):
        """Test get_term is case insensitive."""
        result_lower = get_term("rsi")
        result_upper = get_term("RSI")

        assert result_lower is not None
        assert result_upper is not None
        assert result_lower.name == result_upper.name
