"""
毎晩22時にClaudeでプロラインフリーのアフィリエイト投稿文を生成し、Xに自動投稿するスクリプト。
ターゲット：サラリーマン・OL
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

# アフィリエイトリンク
AFFILIATE_URL = "https://povfhbgm.proline.blog"

# 過去投稿ログ（ネタ被り防止用）
HISTORY_FILE = Path(__file__).parent / "history.json"

# サブテーマ（毎回ランダムで1つ選ぶ）
TOPICS = [
    "残業ばかりだった頃に気づいたこと",
    "副業を始めて半年で変わったこと",
    "毎日同じ作業をやめてみた話",
    "お金より時間が欲しいと思った瞬間",
    "SNS集客に疲れていた頃の話",
    "「頑張る」をやめてみた結果",
    "仕組み化という言葉の意味、最近わかった話",
    "会社員のまま収入を増やしてみて感じたこと",
    "貯金が増えない理由にようやく気づいた話",
    "毎晩のルーティンを変えてみた話",
    "「とりあえず行動」をやめた理由",
    "1年前の自分に伝えたいこと",
    "頑張らなくても回る仕組みの正体",
    "副業疲れから抜け出した話",
    "夜の時間の使い方を変えてみた話",
]

# 投稿文生成プロンプト
PROMPT_TEMPLATE = """あなたは会社員として働きながら、副業や自分の時間の使い方について日々考えていることをXに投稿している、ごく普通の個人です。

# 今回のテーマ
{topic}

# 投稿のトーン
- 友人や日記に向けて書くような、自然な一人称のつぶやき
- 押し売り・宣伝・「おすすめします」「詳しくはこちら」のような表現は一切使わない
- 商品名・サービス名・「副業」を売り込む文脈は出さない
- 「〜という気づきがあった」「〜にしてみた」など、個人の経験・感想として書く
- 読んだ人が思わず共感したり、続きが気になったりするような内容
- 絵文字・ハッシュタグは使わない

# 絶対ルール
- 本文は{max_chars}文字以内
- 改行を使って読みやすく整える
- 以下の過去投稿と似た表現・導入を絶対に避ける

# 過去投稿（直近）
{recent_posts}

# 出力
本文のみを出力してください。URLは含めないでください。前置き・説明文は一切不要です。"""


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
    """ClaudeでX投稿の本文を生成（URLは別途付与）"""
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Twitter上でURLは23文字扱い → 本文は140-23-改行1文字=116文字以内
    max_chars = 116

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
                    max_chars=max_chars,
                ),
            }
        ],
    )
    body = message.content[0].text.strip()

    # URLを末尾に付与
    return f"{body}\n{AFFILIATE_URL}"


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

    # 本文部分（URL除く）の文字数チェック
    body = post_text.replace(f"\n{AFFILIATE_URL}", "")
    if len(body) > 116:
        print(f"文字数超過（{len(body)}文字）。再生成します。")
        post_text = generate_post(topic, recent_texts)
        body = post_text.replace(f"\n{AFFILIATE_URL}", "")
        if len(body) > 116:
            # それでも超えたら末尾を切る
            body = body[:115] + "…"
            post_text = f"{body}\n{AFFILIATE_URL}"

    # Xに投稿
    tweet_id = post_to_x(post_text)
    print(f"投稿成功: https://x.com/i/status/{tweet_id}")

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
