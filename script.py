import os
import time
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Set

import feedparser
from twilio.rest import Client
from dotenv import load_dotenv


@dataclass
class NewsItem:
    title: str
    link: str
    published: str
    summary: Optional[str] = None
    image: Optional[str] = None


class WhatsAppRSSBot:
    DAILY_LIMIT = 9
    COUNT_FILE = "daily_count.json"
    # only send items whose title contains one of these keywords
    FILTER_KEYWORDS = ["anime", "premiere", "episode", "season", "release"]

    def __init__(self, feed_url: str):
        load_dotenv()
        self.feed_url      = feed_url
        self.seen_file     = "seen_ids.txt"
        self.seen: Set[str]= self._load_seen()

        # Daily send count
        self.today_str, self.sent_count = self._load_daily_count()

        # Twilio / WhatsApp creds
        self.client        = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        self.from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")
        self.to_whatsapp   = os.getenv("TWILIO_WHATSAPP_TO")

    def _load_seen(self) -> Set[str]:
        if not os.path.exists(self.seen_file):
            return set()
        with open(self.seen_file, "r") as f:
            return set(line.strip() for line in f)

    def _save_seen(self):
        with open(self.seen_file, "w") as f:
            for eid in sorted(self.seen):
                f.write(eid + "\n")

    def _load_daily_count(self):
        today = datetime.now(timezone.utc).date().isoformat()
        if os.path.exists(self.COUNT_FILE):
            with open(self.COUNT_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == today:
                return today, data.get("count", 0)
        return today, 0

    def _save_daily_count(self):
        data = {"date": self.today_str, "count": self.sent_count}
        with open(self.COUNT_FILE, "w") as f:
            json.dump(data, f)

    def fetch_feed(self):
        feed = feedparser.parse(self.feed_url)
        new_items = []
        for entry in feed.entries:
            uid = getattr(entry, "id", entry.link)
            if uid in self.seen:
                continue

            title_lower = entry.title.lower()
            # only include if title contains at least one FILTER_KEYWORDS
            if not any(kw in title_lower for kw in self.FILTER_KEYWORDS):
                continue

            item = NewsItem(
                title      = entry.title,
                link       = entry.link,
                published  = entry.get("published", datetime.now(timezone.utc).isoformat()),
                summary    = self._clean_summary(entry.get("summary", "")),
                image      = self._extract_image(entry)
            )
            new_items.append(item)
            self.seen.add(uid)

        return new_items

    def _clean_summary(self, html: str, max_len: int = 200) -> str:
        import re
        text = re.sub(r"<[^>]+>", "", html).strip()
        if len(text) > max_len:
            text = text[: max_len - 3].rsplit(" ", 1)[0] + "..."
        return text

    def _extract_image(self, entry) -> Optional[str]:
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image/"):
                    return enc.get("href")
        if hasattr(entry, "media_content") and entry.media_content:
            return entry.media_content[0].get("url")
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            return entry.media_thumbnail[0].get("url")
        import re
        m = re.search(r'<img[^>]+src="([^">]+)"', entry.get("summary", ""))
        if m:
            return m.group(1)
        return None

    def send_whatsapp(self, item: NewsItem):
        header = "📰 *Nakama News 中間ニュース Anime Release Update * 📢\n"
        body   = (
            f"{header}"
            f"*{item.title}*\n"
            f"_Published: {item.published}_\n\n"
            f"{item.summary}\n\n"
            f"👉 Read more: {item.link}"
        )

        kwargs = {
            'from_': self.from_whatsapp,
            'to':    self.to_whatsapp,
            'body':  body
        }
        if item.image:
            kwargs['media_url'] = [item.image]

        msg = self.client.messages.create(**kwargs)
        print(f"Sent SID: {msg.sid}")

    def run(self):
        new_posts = self.fetch_feed()
        if not new_posts:
            print("No new anime-release items.")
        for post in new_posts:
            if self.sent_count >= self.DAILY_LIMIT:
                print(f"Daily limit of {self.DAILY_LIMIT} reached; stopping further messages.")
                break
            try:
                self.send_whatsapp(post)
                self.sent_count += 1
                self._save_daily_count()
                time.sleep(1)
            except Exception as e:
                print("Failed to send:", e)
        self._save_seen()


if __name__ == "__main__":
    RSS_URL = "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss"
    bot = WhatsAppRSSBot(RSS_URL)
    bot.run()
