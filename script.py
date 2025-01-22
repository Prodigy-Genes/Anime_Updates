import time
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional
import telebot
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

@dataclass
class NewsItem:
    title: str
    link: str
    timestamp: str
    image_url: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None

class CrunchyrollBot:
    def __init__(self):
        load_dotenv()
        self.bot_token = os.getenv("BOT_TOKEN")
        if not self.bot_token:
            raise ValueError("Bot token is not set in the .env file.")
        
        
        self.seen_articles = set()
        self.setup_logging()
        self.bot = telebot.TeleBot(self.bot_token)
        self.setup_handlers()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler('bot.log'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger(__name__)

    def setup_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start(message):
            self.bot.reply_to(message, "Starting news fetch...")
            self.fetch_and_send_news(message.chat.id)

        @self.bot.message_handler(commands=['help'])
        def help(message):
            help_text = (
                "Available commands:\n"
                "/start - Fetch latest anime news\n"
                "/help - Show this help message"
            )
            self.bot.reply_to(message, help_text)

    def setup_driver(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920x1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def extract_article_data(self, article) -> Optional[NewsItem]:
        try:
            html = article.get_attribute('outerHTML')
            soup = BeautifulSoup(html, 'html.parser')
            
            title = (
                article.find_element(By.CSS_SELECTOR, 'h2, h3').text.strip() or
                soup.find(['h2', 'h3']).text.strip()
            )
            
            link = (
                article.find_element(By.CSS_SELECTOR, 'a').get_attribute('href') or
                soup.find('a')['href']
            )
            
            image_url = None
            try:
                image_elem = article.find_element(By.CSS_SELECTOR, 'img')
                image_url = image_elem.get_attribute('src')
            except:
                try:
                    image_elem = soup.find('img')
                    image_url = image_elem['src'] if image_elem else None
                except:
                    pass

            return NewsItem(
                title=title,
                link=link,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                image_url=image_url
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting article data: {e}")
            return None

    def fetch_news(self) -> List[NewsItem]:
        driver = self.setup_driver()
        anime_data = []
        
        try:
            driver.get("https://www.crunchyroll.com/news")
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'article')))
            articles = driver.find_elements(By.CSS_SELECTOR, 'article')
            
            for article in articles:
                news_item = self.extract_article_data(article)
                if news_item and self.is_relevant_news(news_item.title):
                    if news_item.link not in self.seen_articles:
                        anime_data.append(news_item)
                        self.seen_articles.add(news_item.link)
            
        except Exception as e:
            self.logger.error(f"Error fetching data: {e}")
        finally:
            driver.quit()
            
        return anime_data

    def is_relevant_news(self, text: str) -> bool:
        keywords = {
            'release', 'premiere', 'debut', 'announces', 'coming',
            'launches', 'airs', 'season', 'streaming', 'schedule',
            'date', 'reveals', 'announced', 'trailer', 'preview',
            'exclusive', 'first look'
        }
        return any(keyword.lower() in text.lower() for keyword in keywords)

    def fetch_and_send_news(self, chat_id):
        news = self.fetch_news()
        if not news:
            self.bot.send_message(chat_id, "No new articles found.")
            return

        for item in news:
            try:
                if item.image_url:
                    caption = f"🎯 {item.title}\n🔗 {item.link}\n⏰ {item.timestamp}"
                    self.bot.send_photo(chat_id, item.image_url, caption=caption)
                else:
                    text = f"🎯 {item.title}\n🔗 {item.link}\n⏰ {item.timestamp}"
                    self.bot.send_message(chat_id, text, disable_web_page_preview=False)
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"Error sending message: {e}")

    def run(self):
        self.logger.info("Bot started")
        self.bot.infinity_polling()

def main():
    bot = CrunchyrollBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")

if __name__ == "__main__":
    main()