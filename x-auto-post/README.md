# X 自動投稿システム（睡眠改善ネタ）

毎晩22:00（JST）に Claude が睡眠改善の投稿文を生成し、X に自動投稿します。

## 構成

```
GitHub Actions (毎日22時)
   ↓
post.py
   ├─ Claude API で投稿文生成（型①：共感→原因→ミニ改善）
   └─ X API v2 で投稿
   ↓
history.json に記録（ネタ被り防止）
```

## セットアップ手順

### 1. X（Twitter）API キーを取得

1. <https://developer.x.com/> にアクセスし、X アカウントでログイン
2. 「Sign up for Free Account」をクリックし、開発者アカウントを作成
   - 利用目的を英語250文字以上で入力する必要あり（例：`I will use this API to post daily tips about sleep improvement for my personal blog audience.`）
3. 承認後、ダッシュボードで **Projects & Apps → Overview → Create App**
4. App 名を決めて作成
5. **User authentication settings** を設定：
   - App permissions: **Read and write**（← 重要。Read だけだと投稿できません）
   - Type of App: **Web App, Automated App or Bot**
   - Callback URI: `https://example.com`（使わないので仮でOK）
   - Website URL: 任意
6. **Keys and tokens** タブから以下4つを取得：
   - `API Key` → `X_API_KEY`
   - `API Key Secret` → `X_API_SECRET`
   - `Access Token` → `X_ACCESS_TOKEN`
   - `Access Token Secret` → `X_ACCESS_TOKEN_SECRET`

> ⚠️ Access Token は権限を **Read and write** に変更した**後**に再生成してください。古いトークンはRead権限のままで、投稿できません。

### 2. GitHub Secrets に登録

リポジトリの **Settings → Secrets and variables → Actions → New repository secret** で以下5つを登録：

| Secret 名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API キー（既存のもの） |
| `X_API_KEY` | 上記1で取得 |
| `X_API_SECRET` | 上記1で取得 |
| `X_ACCESS_TOKEN` | 上記1で取得 |
| `X_ACCESS_TOKEN_SECRET` | 上記1で取得 |

### 3. GitHub Actions を有効化

- **Settings → Actions → General → Workflow permissions** で
  **Read and write permissions** を選択（履歴ファイルの自動コミットに必要）
- リポジトリを GitHub にプッシュすれば、毎晩22時に自動実行されます

### 4. 動作確認（手動実行）

- GitHub リポジトリの **Actions タブ → Daily X Auto Post → Run workflow**
- 手動で1回実行してテストできます

## ローカルで試す

```bash
cd x-auto-post
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...
export X_API_KEY=...
export X_API_SECRET=...
export X_ACCESS_TOKEN=...
export X_ACCESS_TOKEN_SECRET=...

python post.py
```

## カスタマイズ

### テーマを増やす
`post.py` の `TOPICS` リストに追加してください。

### 投稿時刻を変える
`.github/workflows/daily-post.yml` の cron を編集：
- cron は **UTC** で記述します
- JST から 9時間引いた時刻を指定
- 例：毎朝8時JST → `0 23 * * *`（前日23時UTC）

### 投稿の型を変える
`post.py` の `PROMPT_TEMPLATE` を編集してください。

## 注意事項

- X API の Free プランは **月1,500投稿まで**。毎日1投稿なら余裕です
- Claude API は毎回呼び出すので、従量課金が発生します（1投稿あたり数円以下）
- `history.json` は自動でコミットされるため、履歴はリポジトリに残ります
