import os
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
import xml.dom.minidom

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://dime.jp"
GENRE_URL = "https://dime.jp/genre/"
FEED_PATH = Path("docs/feed.xml")
EXCLUDED_PATH = Path("excluded_articles.json")
EXCLUDE_WORDS_PATH = Path("exclude_words.txt")

JST = timezone(timedelta(hours=9))


def load_exclude_words() -> list[str]:
    if not EXCLUDE_WORDS_PATH.exists():
        return []
    words = []
    for line in EXCLUDE_WORDS_PATH.read_text(encoding="utf-8").splitlines():
        word = line.strip()
        if word and not word.startswith("#"):
            words.append(word)
    return words


def scrape_articles() -> list[dict]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(GENRE_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    articles = []
    seen_urls = set()

    # dime.jp の記事リンクを収集（/genre/*** の形式）
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # 絶対URLに変換
        if href.startswith("/"):
            href = BASE_URL + href
        if not href.startswith(BASE_URL):
            continue

        # 記事URLのパターン: /genre/数字/ のみ（タグ・ページネーション除外）
        if not re.fullmatch(r"https://dime\.jp/genre/\d+/", href):
            continue

        if href in seen_urls:
            continue
        seen_urls.add(href)

        # タイトルを取得（a タグのテキスト or 親要素のタイトル系要素）
        title = a_tag.get_text(strip=True)
        if not title:
            # 画像のalt属性を試みる
            img = a_tag.find("img")
            if img:
                title = img.get("alt", "").strip()
        if not title:
            continue

        articles.append({"title": title, "url": href})

    return articles


def filter_articles(
    articles: list[dict], exclude_words: list[str]
) -> tuple[list[dict], list[dict]]:
    included = []
    excluded = []
    for article in articles:
        matched = any(word in article["title"] for word in exclude_words)
        if matched:
            excluded.append(article)
        else:
            included.append(article)
    return included, excluded


def save_excluded(excluded: list[dict]) -> None:
    now = datetime.now(JST).isoformat()
    data = {"updated": now, "articles": excluded}
    EXCLUDED_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_rss(articles: list[dict]) -> str:
    now = datetime.now(JST)
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S %z")

    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "DIME.jp 最新記事"
    SubElement(channel, "link").text = GENRE_URL
    SubElement(channel, "description").text = "DIME.jpの最新記事フィード（除外ワードフィルタ済み）"
    SubElement(channel, "language").text = "ja"
    SubElement(channel, "lastBuildDate").text = pub_date
    SubElement(channel, "ttl").text = "60"

    for article in articles:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = article["title"]
        SubElement(item, "link").text = article["url"]
        SubElement(item, "guid", isPermaLink="true").text = article["url"]
        SubElement(item, "pubDate").text = pub_date

    xml_str = tostring(rss, encoding="unicode", xml_declaration=False)
    pretty = xml.dom.minidom.parseString(
        '<?xml version="1.0" encoding="UTF-8"?>' + xml_str
    ).toprettyxml(indent="  ", encoding=None)

    # toprettyxml が先頭に <?xml ?> を重複追加するので最初の宣言のみ残す
    lines = pretty.splitlines()
    if lines[0].startswith("<?xml") and lines[1].startswith("<?xml"):
        lines = lines[1:]
    return "\n".join(lines)


def main() -> None:
    print("スクレイピング開始...")
    articles = scrape_articles()
    print(f"  取得記事数: {len(articles)}")

    exclude_words = load_exclude_words()
    print(f"  除外ワード数: {len(exclude_words)}")

    included, excluded = filter_articles(articles, exclude_words)
    print(f"  フィルタ後: {len(included)} 件 / 除外: {len(excluded)} 件")

    FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    feed_xml = build_rss(included)
    FEED_PATH.write_text(feed_xml, encoding="utf-8")
    print(f"  RSS出力: {FEED_PATH}")

    save_excluded(excluded)
    print(f"  除外リスト保存: {EXCLUDED_PATH}")


if __name__ == "__main__":
    main()
