import os
import time
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
    def __init__(self, feed_url: str):
        load_dotenv()
        self.feed_url      = feed_url
        self.seen_file     = "seen_ids.txt"
        self.seen: Set[str]= self._load_seen()

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

    def fetch_feed(self):
        feed = feedparser.parse(self.feed_url)
        new_items = []
        for entry in feed.entries:
            uid = getattr(entry, "id", entry.link)
            if uid in self.seen:
                continue

            item = NewsItem(
                title      = entry.title,
                link       = entry.link,
                published  = entry.get("published", datetime.now(timezone.utc).isoformat()),
                summary    = self._clean_summary(entry.get("summary", "")),
                image      = self._extract_image(entry)
            )
            # Debug: print available image URL
            print(f"Extracted image URL: {item.image}")
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
        # 1) Try RSS enclosure
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image/"):
                    return enc.get("href")
        # 2) Try media_content
        if hasattr(entry, "media_content") and entry.media_content:
            return entry.media_content[0].get("url")
        # 3) Try media_thumbnail
        if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
            return entry.media_thumbnail[0].get("url")
        # 4) Fallback: parse <img> in summary
        import re
        m = re.search(r'<img[^>]+src="([^">]+)"', entry.get("summary", ""))
        if m:
            return m.group(1)
        return None

    def send_whatsapp(self, item: NewsItem):
        header = "📰 *Nakama News 中間ニュース Update * 📢\n"
        body   = (
            f"{header}"
            f"*{item.title}*\n"
            f"_Published: {item.published}_\n\n"
            f"{item.summary}\n\n"
            f"👉 Read more: {item.link}"
        )

        # Log sending attempt
        print(f"Sending message: {item.title}\nImage URL: {item.image}")

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
            print("No new items.")
        for post in new_posts:
            try:
                self.send_whatsapp(post)
                time.sleep(1)
            except Exception as e:
                print("Failed to send:", e)
        self._save_seen()


if __name__ == "__main__":
    RSS_URL = "https://cr-news-api-service.prd.crunchyrollsvc.com/v1/en-US/rss"
    bot = WhatsAppRSSBot(RSS_URL)
    bot.run()
# This script fetches RSS feed items and sends them via WhatsApp using Twilio API.
# It handles image extraction from the feed and formats the message for WhatsApp.