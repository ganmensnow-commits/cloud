"""
毎晩22時にClaudeで睡眠改善ネタを生成し、Xに自動投稿するスクリプト。
GitHub Actionsから実行される想定。
"""

import os
import json
import random
from datetime import datetime
from pathlib import Path

import tweepy
from anthropic import Anthropic

# ========== 設定 ==========

# 過去投稿ログ（ネタ被り防止用）
HISTORY_FILE = Path(__file__).parent / "history.json"

# 睡眠改善のサブテーマ（毎回ランダムで1つ選ぶ → 被り防止）
TOPICS = [
    "寝る直前のスマホ・ブルーライト",
    "深部体温と入浴タイミング",
    "寝室の光（豆電球・遮光）",
    "寝室の音・生活音",
    "カフェインの摂取タイミング",
    "寝具（枕の高さ・マットレスの硬さ）",
    "寝る前の食事・アルコール",
    "朝の光と体内時計",
    "寝る前のストレッチ・呼吸法",
    "寝室の温度・湿度",
    "二度寝・アラームの使い方",
    "昼寝の正しい取り方",
    "就寝前のルーティン",
    "自律神経と副交感神経",
    "睡眠負債と週末の寝だめ",
]

# 投稿文生成プロンプト（型①：共感 → 原因 → ミニ改善）
PROMPT_TEMPLATE = """あなたは睡眠改善に詳しい発信者として、X（旧Twitter）に投稿する文章を作成します。

# 今回のテーマ
{topic}

# 構造（型①：共感 → 原因 → ミニ改善）
1. 1〜2行目：読者の独り言を代弁する、刺さる共感フック
2. 中盤：科学的根拠を感じさせる"原因"の説明（専門用語を1つだけ自然に入れる）
3. 最後：今夜すぐ試せるミニ改善アクション1つ

# 絶対ルール
- 商品名やブランド名は一切出さない（"睡眠に詳しい人"というポジション作りが目的）
- 140文字以内（日本語・改行含む）
- 絵文字・ハッシュタグは使わない
- 語り口は柔らかく、でも断定的に信頼感を出す
- 改行を使って読みやすく整える
- 以下の過去投稿と似た表現・導入を絶対に避ける

# 過去投稿（直近）
{recent_posts}

# 出力
投稿文のみを出力してください。前置き・後書き・説明文は一切不要です。"""


def load_history() -> list[dict]:
    """過去投稿履歴を読み込む"""
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def save_history(history: list[dict]) -> None:
    """履歴を保存する（直近30件のみ保持）"""
    HISTORY_FILE.write_text(
        json.dumps(history[-30:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def generate_post(topic: str, recent_posts: list[str]) -> str:
    """ClaudeでX投稿文を生成"""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # 過去投稿を文字列化（空ならその旨）
    recent_text = "\n---\n".join(recent_posts[-5:]) if recent_posts else "（まだありません）"

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(
                    topic=topic,
                    recent_posts=recent_text,
                ),
            }
        ],
    )
    return message.content[0].text.strip()


def post_to_x(text: str) -> str:
    """X API v2 で投稿する"""
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    response = client.create_tweet(text=text)
    return response.data["id"]


def main() -> None:
    # 過去投稿を取得
    history = load_history()
    used_topics = {h["topic"] for h in history[-10:]}  # 直近10件のテーマは避ける

    # 未使用のテーマからランダム選択
    available = [t for t in TOPICS if t not in used_topics]
    if not available:
        available = TOPICS  # 全部使い切ったらリセット
    topic = random.choice(available)

    print(f"[テーマ] {topic}")

    # 投稿文を生成
    recent_texts = [h["text"] for h in history]
    post_text = generate_post(topic, recent_texts)
    print(f"[生成された投稿]\n{post_text}\n")

    # 140文字超過チェック（Claudeがたまに超える場合のセーフティ）
    if len(post_text) > 140:
        print(f"⚠️ 140文字超過（{len(post_text)}文字）。再生成します。")
        post_text = generate_post(topic, recent_texts)
        if len(post_text) > 140:
            # それでも超えたら末尾を切る
            post_text = post_text[:139] + "…"

    # Xに投稿
    tweet_id = post_to_x(post_text)
    print(f"✅ 投稿成功: https://x.com/i/status/{tweet_id}")

    # 履歴に追加
    history.append(
        {
            "date": datetime.now().isoformat(),
            "topic": topic,
            "text": post_text,
            "tweet_id": tweet_id,
        }
    )
    save_history(history)


if __name__ == "__main__":
    main()
