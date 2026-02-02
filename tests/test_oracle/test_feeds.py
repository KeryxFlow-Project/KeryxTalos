"""Tests for news feeds aggregator."""

from datetime import UTC, datetime, timedelta

import pytest

from keryxflow.oracle.feeds import (
    CryptoPanicFetcher,
    NewsAggregator,
    NewsDigest,
    NewsItem,
    NewsSentiment,
    RSSFetcher,
)


@pytest.fixture
def sample_news_item():
    """Create a sample news item."""
    return NewsItem(
        title="Bitcoin Hits New All-Time High",
        source="CryptoNews",
        url="https://example.com/btc-ath",
        published=datetime.now(UTC) - timedelta(hours=1),
        summary="Bitcoin has reached a new all-time high above $100k",
        sentiment=NewsSentiment.BULLISH,
        currencies=["BTC"],
    )


@pytest.fixture
def sample_news_items():
    """Create a list of sample news items."""
    now = datetime.now(UTC)
    return [
        NewsItem(
            title="Bitcoin Hits New ATH",
            source="CryptoNews",
            url="https://example.com/1",
            published=now - timedelta(hours=1),
            sentiment=NewsSentiment.BULLISH,
            currencies=["BTC"],
        ),
        NewsItem(
            title="ETH 2.0 Update Delayed",
            source="CryptoDaily",
            url="https://example.com/2",
            published=now - timedelta(hours=2),
            sentiment=NewsSentiment.BEARISH,
            currencies=["ETH"],
        ),
        NewsItem(
            title="Market Analysis",
            source="Decrypt",
            url="https://example.com/3",
            published=now - timedelta(hours=3),
            sentiment=NewsSentiment.NEUTRAL,
            currencies=["BTC", "ETH"],
        ),
    ]


class TestNewsItem:
    """Tests for NewsItem."""

    def test_to_dict(self, sample_news_item):
        """Test NewsItem.to_dict()."""
        data = sample_news_item.to_dict()

        assert data["title"] == "Bitcoin Hits New All-Time High"
        assert data["source"] == "CryptoNews"
        assert data["sentiment"] == "bullish"
        assert "BTC" in data["currencies"]

    def test_age_hours(self, sample_news_item):
        """Test NewsItem.age_hours property."""
        # News is 1 hour old
        assert 0.9 < sample_news_item.age_hours < 1.1


class TestNewsDigest:
    """Tests for NewsDigest."""

    def test_to_dict(self, sample_news_items):
        """Test NewsDigest.to_dict()."""
        digest = NewsDigest(
            items=sample_news_items,
            timestamp=datetime.now(UTC),
            overall_sentiment=NewsSentiment.BULLISH,
            sentiment_score=0.3,
            summary="Market is generally positive",
        )

        data = digest.to_dict()

        assert len(data["items"]) == 3
        assert data["overall_sentiment"] == "bullish"
        assert data["sentiment_score"] == 0.3
        assert data["summary"] == "Market is generally positive"


class TestRSSFetcher:
    """Tests for RSSFetcher."""

    def test_detect_currencies_btc(self):
        """Test currency detection for Bitcoin."""
        fetcher = RSSFetcher([])
        text = "Bitcoin price surges past $100k as BTC adoption grows"
        currencies = fetcher._detect_currencies(text)
        assert "BTC" in currencies

    def test_detect_currencies_multiple(self):
        """Test detection of multiple currencies."""
        fetcher = RSSFetcher([])
        text = "Bitcoin and Ethereum lead market rally as Solana follows"
        currencies = fetcher._detect_currencies(text)
        assert "BTC" in currencies
        assert "ETH" in currencies
        assert "SOL" in currencies

    def test_detect_currencies_none(self):
        """Test when no currencies are mentioned."""
        fetcher = RSSFetcher([])
        text = "General market news about stocks and bonds"
        currencies = fetcher._detect_currencies(text)
        assert len(currencies) == 0

    def test_clean_html(self):
        """Test HTML cleaning."""
        fetcher = RSSFetcher([])
        html = "<p>Hello <strong>World</strong></p>"
        clean = fetcher._clean_html(html)
        assert clean == "Hello World"

    def test_parse_date_iso_format(self):
        """Test ISO date parsing."""
        fetcher = RSSFetcher([])
        date_str = "2024-01-15T10:30:00Z"
        result = fetcher._parse_date(date_str)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_empty(self):
        """Test empty date returns current time."""
        fetcher = RSSFetcher([])
        result = fetcher._parse_date("")
        assert isinstance(result, datetime)
        # Should be close to now
        assert (datetime.now(UTC) - result).total_seconds() < 5


class TestCryptoPanicFetcher:
    """Tests for CryptoPanicFetcher."""

    def test_votes_to_sentiment_bullish(self):
        """Test bullish sentiment detection from votes."""
        fetcher = CryptoPanicFetcher("")
        votes = {"positive": 10, "negative": 2}
        sentiment = fetcher._votes_to_sentiment(votes)
        assert sentiment == NewsSentiment.BULLISH

    def test_votes_to_sentiment_bearish(self):
        """Test bearish sentiment detection from votes."""
        fetcher = CryptoPanicFetcher("")
        votes = {"positive": 2, "negative": 10}
        sentiment = fetcher._votes_to_sentiment(votes)
        assert sentiment == NewsSentiment.BEARISH

    def test_votes_to_sentiment_neutral(self):
        """Test neutral sentiment when votes are balanced."""
        fetcher = CryptoPanicFetcher("")
        votes = {"positive": 5, "negative": 5}
        sentiment = fetcher._votes_to_sentiment(votes)
        assert sentiment == NewsSentiment.NEUTRAL

    def test_votes_to_sentiment_unknown(self):
        """Test unknown sentiment when no votes."""
        fetcher = CryptoPanicFetcher("")
        votes = {}
        sentiment = fetcher._votes_to_sentiment(votes)
        assert sentiment == NewsSentiment.UNKNOWN

    async def test_fetch_skips_without_api_key(self):
        """Test that fetch returns empty list without API key."""
        fetcher = CryptoPanicFetcher("")
        result = await fetcher.fetch()
        assert result == []


class TestNewsAggregator:
    """Tests for NewsAggregator."""

    async def test_calculate_sentiment_bullish(self):
        """Test sentiment calculation for bullish news."""
        aggregator = NewsAggregator()
        now = datetime.now(UTC)

        items = [
            NewsItem(
                title="BTC Up",
                source="Test",
                url="",
                published=now - timedelta(hours=1),
                sentiment=NewsSentiment.BULLISH,
            ),
            NewsItem(
                title="BTC Up More",
                source="Test",
                url="",
                published=now - timedelta(hours=2),
                sentiment=NewsSentiment.BULLISH,
            ),
        ]

        sentiment, score = aggregator._calculate_sentiment(items)
        assert sentiment == NewsSentiment.BULLISH
        assert score > 0

    async def test_calculate_sentiment_bearish(self):
        """Test sentiment calculation for bearish news."""
        aggregator = NewsAggregator()
        now = datetime.now(UTC)

        items = [
            NewsItem(
                title="BTC Down",
                source="Test",
                url="",
                published=now - timedelta(hours=1),
                sentiment=NewsSentiment.BEARISH,
            ),
            NewsItem(
                title="BTC Down More",
                source="Test",
                url="",
                published=now - timedelta(hours=2),
                sentiment=NewsSentiment.BEARISH,
            ),
        ]

        sentiment, score = aggregator._calculate_sentiment(items)
        assert sentiment == NewsSentiment.BEARISH
        assert score < 0

    async def test_calculate_sentiment_empty(self):
        """Test sentiment calculation with no items."""
        aggregator = NewsAggregator()
        sentiment, score = aggregator._calculate_sentiment([])
        assert sentiment == NewsSentiment.NEUTRAL
        assert score == 0.0

    def test_generate_summary(self, sample_news_items):
        """Test summary generation."""
        aggregator = NewsAggregator()
        summary = aggregator._generate_summary(sample_news_items, NewsSentiment.BULLISH)
        assert "positive" in summary
        assert len(summary) > 0

    def test_generate_summary_empty(self):
        """Test summary generation with no items."""
        aggregator = NewsAggregator()
        summary = aggregator._generate_summary([], NewsSentiment.NEUTRAL)
        assert "No recent news" in summary

    def test_format_for_llm(self, sample_news_items):
        """Test LLM formatting."""
        aggregator = NewsAggregator()
        digest = NewsDigest(
            items=sample_news_items,
            timestamp=datetime.now(UTC),
            overall_sentiment=NewsSentiment.BULLISH,
            sentiment_score=0.5,
        )

        formatted = aggregator.format_for_llm(digest, max_items=2)

        assert "News Digest" in formatted
        assert "bullish" in formatted.lower()
        assert "Bitcoin" in formatted

    def test_cache_validity(self):
        """Test cache validity check."""
        aggregator = NewsAggregator()

        # Initially, cache should be invalid
        assert not aggregator._is_cache_valid()

        # Set cache
        aggregator._cache_time = datetime.now(UTC)
        aggregator._cache = NewsDigest(
            items=[],
            timestamp=datetime.now(UTC),
            overall_sentiment=NewsSentiment.NEUTRAL,
            sentiment_score=0.0,
        )

        # Now cache should be valid
        assert aggregator._is_cache_valid()

        # Expire cache
        aggregator._cache_time = datetime.now(UTC) - timedelta(minutes=10)
        assert not aggregator._is_cache_valid()
