import json
import os
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from pathlib import Path

EXCLUDED_PATH = Path("excluded_articles.json")
JST = timezone(timedelta(hours=9))

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
NOTIFY_TO = os.environ.get("NOTIFY_TO", GMAIL_USER)


def load_excluded() -> list[dict]:
    if not EXCLUDED_PATH.exists():
        return []
    data = json.loads(EXCLUDED_PATH.read_text(encoding="utf-8"))
    return data.get("articles", [])


def build_body(articles: list[dict]) -> str:
    if not articles:
        return "本日の除外記事はありませんでした。"
    lines = ["以下の記事が除外ワードにより除外されました。\n"]
    for i, article in enumerate(articles, 1):
        lines.append(f"{i}. {article['title']}")
        lines.append(f"   {article['url']}\n")
    return "\n".join(lines)


def send_mail(subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = NOTIFY_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def main() -> None:
    articles = load_excluded()
    today = datetime.now(JST).strftime("%Y-%m-%d")
    subject = f"DIME RSS除外記事 ({today})"
    body = build_body(articles)

    print(f"通知送信: {NOTIFY_TO} / 除外記事数: {len(articles)}")
    send_mail(subject, body)
    print("送信完了")


if __name__ == "__main__":
    main()
