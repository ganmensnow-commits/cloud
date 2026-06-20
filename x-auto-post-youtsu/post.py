"""
腰痛セルフケアアカウント 自動投稿スクリプト。
posts.jsonに用意した10投稿を順番通りに1日1件投稿する。
画像ファイル（images/XX.png）が存在すれば一緒に投稿する。
GitHub Actionsから実行される想定。
"""

import json
import os
import requests
from pathlib import Path

import tweepy

# ========== 設定 ==========

BASE_DIR    = Path(__file__).parent
POSTS_FILE  = BASE_DIR / "posts.json"
INDEX_FILE  = BASE_DIR / "current_index.json"
IMAGES_DIR  = BASE_DIR / "images"


def load_posts() -> list[dict]:
    """投稿リストを読み込む"""
    return json.loads(POSTS_FILE.read_text(encoding="utf-8"))


def load_index() -> int:
    """次に投稿するインデックスを読み込む（なければ0から開始）"""
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text(encoding="utf-8")).get("index", 0)
    return 0


def save_index(index: int) -> None:
    """次回用のインデックスを保存する"""
    INDEX_FILE.write_text(
        json.dumps({"index": index}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def upload_image(client_v1: tweepy.API, image_path: Path) -> str | None:
    """画像をX（v1.1）にアップロードしてmedia_idを返す"""
    try:
        media = client_v1.media_upload(filename=str(image_path))
        print(f"[画像アップロード成功] media_id: {media.media_id_string}")
        return media.media_id_string
    except Exception as e:
        print(f"[画像アップロード失敗] {e}（テキストのみで投稿します）")
        return None


def post_to_x(text: str, media_id: str | None = None) -> str:
    """X API v2 で投稿する"""
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    kwargs = {"text": text}
    if media_id:
        kwargs["media_ids"] = [media_id]

    try:
        response = client.create_tweet(**kwargs)
        return response.data["id"]
    except tweepy.errors.Forbidden as e:
        print(f"[403詳細] api_errors: {e.api_errors}")
        print(f"[403詳細] response text: {e.response.text if e.response is not None else 'なし'}")
        raise


def main() -> None:
    posts = load_posts()
    index = load_index()

    # 10投稿を使い切ったら最初に戻る（ループ運用）
    current_index = index % len(posts)
    post = posts[current_index]

    print(f"[投稿番号] {post['id']} / {post['day']} / テーマ：{post['theme']}")
    print(f"[本文]\n{post['text']}\n")

    # 画像ファイルがあればアップロード
    media_id = None
    image_path = IMAGES_DIR / post["image"]
    if image_path.exists():
        # v1.1クライアント（画像アップロード用）
        auth = tweepy.OAuth1UserHandler(
            consumer_key=os.environ["X_API_KEY"],
            consumer_secret=os.environ["X_API_SECRET"],
            access_token=os.environ["X_ACCESS_TOKEN"],
            access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        client_v1 = tweepy.API(auth)
        media_id = upload_image(client_v1, image_path)
    else:
        print(f"[画像なし] {image_path} が見つかりません。テキストのみで投稿します。")

    # Xに投稿
    tweet_id = post_to_x(post["text"], media_id)
    print(f"投稿成功: https://x.com/i/status/{tweet_id}")

    # 次回インデックスを保存
    save_index(index + 1)


if __name__ == "__main__":
    main()
