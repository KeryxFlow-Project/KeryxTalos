"""News feeds aggregator for market context."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import feedparser
import httpx

from keryxflow.config import get_settings
from keryxflow.core.logging import get_logger

logger = get_logger(__name__)


class NewsSentiment(str, Enum):
    """News sentiment classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class NewsSource(str, Enum):
    """News source type."""

    RSS = "rss"
    CRYPTOPANIC = "cryptopanic"


@dataclass
class NewsItem:
    """A single news article."""

    title: str
    source: str
    url: str
    published: datetime
    summary: str = ""
    sentiment: NewsSentiment = NewsSentiment.UNKNOWN
    relevance: float = 0.5  # 0.0 to 1.0
    currencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "source": self.source,
            "url": self.url,
            "published": self.published.isoformat(),
            "summary": self.summary,
            "sentiment": self.sentiment.value,
            "relevance": self.relevance,
            "currencies": self.currencies,
        }

    @property
    def age_hours(self) -> float:
        """Get age of news in hours."""
        return (datetime.now(UTC) - self.published).total_seconds() / 3600


@dataclass
class NewsDigest:
    """Aggregated news digest."""

    items: list[NewsItem]
    timestamp: datetime
    overall_sentiment: NewsSentiment
    sentiment_score: float  # -1.0 (bearish) to 1.0 (bullish)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "items": [item.to_dict() for item in self.items],
            "timestamp": self.timestamp.isoformat(),
            "overall_sentiment": self.overall_sentiment.value,
            "sentiment_score": self.sentiment_score,
            "summary": self.summary,
        }


class RSSFetcher:
    """Fetches news from RSS feeds."""

    def __init__(self, feeds: list[str], timeout: float = 10.0):
        """Initialize RSS fetcher."""
        self.feeds = feeds
        self.timeout = timeout

    async def fetch_all(self, lookback_hours: int = 4) -> list[NewsItem]:
        """Fetch news from all RSS feeds."""
        all_items: list[NewsItem] = []
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)

        for feed_url in self.feeds:
            try:
                items = await self._fetch_feed(feed_url, cutoff)
                all_items.extend(items)
            except Exception as e:
                logger.warning("rss_fetch_failed", feed=feed_url, error=str(e))

        # Sort by published date (newest first)
        all_items.sort(key=lambda x: x.published, reverse=True)

        logger.info("rss_fetch_complete", total_items=len(all_items))
        return all_items

    async def _fetch_feed(self, feed_url: str, cutoff: datetime) -> list[NewsItem]:
        """Fetch a single RSS feed."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(feed_url)
            response.raise_for_status()

        feed = feedparser.parse(response.text)
        items: list[NewsItem] = []

        source_name = feed.feed.get("title", feed_url)

        for entry in feed.entries:
            published = self._parse_date(entry.get("published", entry.get("updated", "")))

            if published < cutoff:
                continue

            # Extract summary
            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary[:500]  # Limit length
            elif hasattr(entry, "description"):
                summary = entry.description[:500]

            # Clean HTML from summary
            summary = self._clean_html(summary)

            # Detect currencies mentioned
            currencies = self._detect_currencies(entry.title + " " + summary)

            items.append(
                NewsItem(
                    title=entry.title,
                    source=source_name,
                    url=entry.link,
                    published=published,
                    summary=summary,
                    currencies=currencies,
                )
            )

        return items

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime."""
        if not date_str:
            return datetime.now(UTC)

        try:
            # feedparser usually provides struct_time
            if hasattr(date_str, "tm_year"):  # struct_time
                return datetime(*date_str[:6], tzinfo=UTC)

            # Try common formats
            formats = [
                "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    return dt
                except ValueError:
                    logger.debug("date_parse_format_mismatch", date_str=date_str, fmt=fmt)
                    continue

            return datetime.now(UTC)
        except Exception:
            logger.warning("date_parse_failed", date_str=date_str, exc_info=True)
            return datetime.now(UTC)

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re

        clean = re.sub(r"<[^>]+>", "", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _detect_currencies(self, text: str) -> list[str]:
        """Detect cryptocurrency mentions in text."""
        currencies = []
        text_upper = text.upper()

        mappings = {
            "BTC": ["BTC", "BITCOIN"],
            "ETH": ["ETH", "ETHEREUM"],
            "SOL": ["SOL", "SOLANA"],
            "XRP": ["XRP", "RIPPLE"],
            "DOGE": ["DOGE", "DOGECOIN"],
            "ADA": ["ADA", "CARDANO"],
            "DOT": ["DOT", "POLKADOT"],
            "AVAX": ["AVAX", "AVALANCHE"],
            "LINK": ["LINK", "CHAINLINK"],
            "MATIC": ["MATIC", "POLYGON"],
        }

        for symbol, keywords in mappings.items():
            for keyword in keywords:
                if keyword in text_upper:
                    if symbol not in currencies:
                        currencies.append(symbol)
                    break

        return currencies


class CryptoPanicFetcher:
    """Fetches news from CryptoPanic API."""

    BASE_URL = "https://cryptopanic.com/api/v1/posts/"

    def __init__(self, api_key: str, timeout: float = 10.0):
        """Initialize CryptoPanic fetcher."""
        self.api_key = api_key
        self.timeout = timeout

    async def fetch(
        self,
        currencies: list[str] | None = None,
        filter_type: str = "hot",
        lookback_hours: int = 4,
    ) -> list[NewsItem]:
        """Fetch news from CryptoPanic."""
        if not self.api_key:
            logger.debug("cryptopanic_skipped", reason="no_api_key")
            return []

        params: dict[str, Any] = {
            "auth_token": self.api_key,
            "public": "true",
            "filter": filter_type,
        }

        if currencies:
            params["currencies"] = ",".join(currencies)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            items = self._parse_response(data, lookback_hours)
            logger.info("cryptopanic_fetch_complete", items=len(items))
            return items

        except Exception as e:
            logger.warning("cryptopanic_fetch_failed", error=str(e))
            return []

    def _parse_response(self, data: dict, lookback_hours: int) -> list[NewsItem]:
        """Parse CryptoPanic API response."""
        items: list[NewsItem] = []
        cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)

        for post in data.get("results", []):
            try:
                published = datetime.fromisoformat(
                    post["published_at"].replace("Z", "+00:00")
                )

                if published < cutoff:
                    continue

                # Map CryptoPanic sentiment to our enum
                votes = post.get("votes", {})
                sentiment = self._votes_to_sentiment(votes)

                # Extract currencies
                currencies = [c["code"] for c in post.get("currencies", [])]

                items.append(
                    NewsItem(
                        title=post["title"],
                        source="CryptoPanic",
                        url=post.get("url", ""),
                        published=published,
                        summary="",  # CryptoPanic doesn't provide summaries
                        sentiment=sentiment,
                        currencies=currencies,
                    )
                )
            except Exception as e:
                logger.debug("cryptopanic_parse_error", error=str(e))
                continue

        return items

    def _votes_to_sentiment(self, votes: dict) -> NewsSentiment:
        """Convert CryptoPanic votes to sentiment."""
        positive = votes.get("positive", 0)
        negative = votes.get("negative", 0)

        if positive > negative * 2:
            return NewsSentiment.BULLISH
        elif negative > positive * 2:
            return NewsSentiment.BEARISH
        elif positive > 0 or negative > 0:
            return NewsSentiment.NEUTRAL
        else:
            return NewsSentiment.UNKNOWN


class NewsAggregator:
    """Aggregates news from multiple sources."""

    def __init__(self) -> None:
        """Initialize the aggregator."""
        self.settings = get_settings()
        oracle_settings = self.settings.oracle

        # Initialize fetchers
        self.rss_fetcher = RSSFetcher(oracle_settings.rss_feeds)
        self.cryptopanic_fetcher = CryptoPanicFetcher(
            self.settings.cryptopanic_api_key.get_secret_value()
        )

        self.lookback_hours = oracle_settings.news_lookback_hours
        self._cache: NewsDigest | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl = 300  # 5 minutes

    async def fetch_news(
        self,
        symbols: list[str] | None = None,
        force_refresh: bool = False,
    ) -> NewsDigest:
        """
        Fetch news from all configured sources.

        Args:
            symbols: Filter for specific trading pairs (e.g., ["BTC/USDT"])
            force_refresh: Force refresh even if cache is valid

        Returns:
            NewsDigest with aggregated news items
        """
        # Check cache
        if not force_refresh and self._is_cache_valid() and self._cache is not None:
            return self._cache

        all_items: list[NewsItem] = []

        # Extract currencies from symbols
        currencies = None
        if symbols:
            currencies = [s.split("/")[0] for s in symbols]

        # Fetch from all sources in parallel
        tasks = []

        if "rss" in self.settings.oracle.news_sources:
            tasks.append(self.rss_fetcher.fetch_all(self.lookback_hours))

        if "cryptopanic" in self.settings.oracle.news_sources:
            tasks.append(
                self.cryptopanic_fetcher.fetch(
                    currencies=currencies,
                    lookback_hours=self.lookback_hours,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                logger.warning("news_fetch_error", error=str(result))

        # Filter by currencies if specified
        if currencies:
            filtered_items = []
            for item in all_items:
                if not item.currencies or any(c in item.currencies for c in currencies):
                    filtered_items.append(item)
            all_items = filtered_items

        # Sort by relevance and date
        all_items.sort(key=lambda x: (x.relevance, x.published), reverse=True)

        # Limit to reasonable number
        all_items = all_items[:50]

        # Calculate overall sentiment
        overall_sentiment, sentiment_score = self._calculate_sentiment(all_items)

        # Generate summary
        summary = self._generate_summary(all_items, overall_sentiment)

        digest = NewsDigest(
            items=all_items,
            timestamp=datetime.now(UTC),
            overall_sentiment=overall_sentiment,
            sentiment_score=sentiment_score,
            summary=summary,
        )

        # Update cache
        self._cache = digest
        self._cache_time = datetime.now(UTC)

        logger.info(
            "news_aggregation_complete",
            total_items=len(all_items),
            sentiment=overall_sentiment.value,
            score=sentiment_score,
        )

        return digest

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self._cache is None or self._cache_time is None:
            return False

        age = (datetime.now(UTC) - self._cache_time).total_seconds()
        return age < self._cache_ttl

    def _calculate_sentiment(
        self, items: list[NewsItem]
    ) -> tuple[NewsSentiment, float]:
        """Calculate overall sentiment from news items."""
        if not items:
            return NewsSentiment.NEUTRAL, 0.0

        bullish = 0
        bearish = 0
        neutral = 0

        for item in items:
            # Weight by recency
            recency_weight = max(0.5, 1.0 - (item.age_hours / 24))

            if item.sentiment == NewsSentiment.BULLISH:
                bullish += recency_weight
            elif item.sentiment == NewsSentiment.BEARISH:
                bearish += recency_weight
            else:
                neutral += recency_weight * 0.5

        total = bullish + bearish + neutral
        if total == 0:
            return NewsSentiment.NEUTRAL, 0.0

        # Calculate score (-1 to 1)
        score = (bullish - bearish) / total

        if score > 0.2:
            sentiment = NewsSentiment.BULLISH
        elif score < -0.2:
            sentiment = NewsSentiment.BEARISH
        else:
            sentiment = NewsSentiment.NEUTRAL

        return sentiment, score

    def _generate_summary(
        self, items: list[NewsItem], sentiment: NewsSentiment
    ) -> str:
        """Generate a brief summary of news."""
        if not items:
            return "No recent news available."

        # Get top headlines
        top_items = items[:3]
        headlines = [item.title for item in top_items]

        sentiment_text = {
            NewsSentiment.BULLISH: "positive",
            NewsSentiment.BEARISH: "negative",
            NewsSentiment.NEUTRAL: "mixed",
            NewsSentiment.UNKNOWN: "unclear",
        }

        return (
            f"Overall sentiment: {sentiment_text[sentiment]}. "
            f"Top headlines: {'; '.join(headlines[:2])}"
        )

    def format_for_llm(self, digest: NewsDigest, max_items: int = 5) -> str:
        """Format news digest for LLM consumption."""
        lines = [
            f"News Digest ({digest.timestamp.strftime('%Y-%m-%d %H:%M')} UTC)",
            f"Overall Sentiment: {digest.overall_sentiment.value} (score: {digest.sentiment_score:+.2f})",
            "",
            "Recent Headlines:",
        ]

        for item in digest.items[:max_items]:
            age = f"{item.age_hours:.1f}h ago"
            currencies = ", ".join(item.currencies) if item.currencies else "general"
            sentiment = f"[{item.sentiment.value}]" if item.sentiment != NewsSentiment.UNKNOWN else ""
            lines.append(f"- [{age}] {item.title} ({currencies}) {sentiment}")

        return "\n".join(lines)


# Global instance
_aggregator: NewsAggregator | None = None


def get_news_aggregator() -> NewsAggregator:
    """Get the global news aggregator instance."""
    global _aggregator
    if _aggregator is None:
        _aggregator = NewsAggregator()
    return _aggregator
