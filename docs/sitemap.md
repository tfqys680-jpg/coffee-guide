# sitemap の更新日と検証

`lastmod` は最後の**実質的なページ更新日（日本時間）**を日単位で記録する。
デプロイ日・CI実行日・コミット日を機械的に採用しない。
本文、Topics、意味のあるリンク、画像や構造化データの更新を確認して決める。
CSS調整、整形、著作権年の更新だけなら日付を維持する。

## 2026-10-21 の調査

調査時の main: `a6b8b8b4be0e20bb221e1029c13f453495fc5229`。
全履歴を確認し、これより後の main の変更はなかった。

| PR / コミット | main への反映日時（JST） | 内容と判断 |
| --- | --- | --- |
| [#9](https://github.com/tfqys680-jpg/coffee-guide/pull/9) / `dfff486` | 2026-10-03 13:28:56 | 豆缶プロジェクトの紹介文と外部リンクをTopicsに追加。実質的な更新。記事内の10月2日とは区別する。 |
| [#10](https://github.com/tfqys680-jpg/coffee-guide/pull/10) / `32bd552` | 2026-10-03 13:43:01 | Instagram投稿6件の見出し・本文・リンクを追加。実質的な更新。投稿自体の日付とは区別する。 |
| [#1](https://github.com/tfqys680-jpg/coffee-guide/pull/1) / `a6b8b8b` | 2026-10-03 13:45:03 | canonical / OGPと配信設定の移行。Topics以降の本文変更なし。 |

したがって `2026-10-03` を採用する。既存の8月20日は、現在の履歴にある
9月以降の本文更新も反映していない。検索表示開始の10月18日、通知の10月21日、
この修正の作業日はコンテンツ更新日として使用しない。
本番配信開始の厳密な時刻まではこの調査では立証していないため、秒単位の値は記載しない。

根拠: [Google公式のsitemapガイド](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap?hl=ja)
（lastmodは最後の重要な更新を反映し、著作権年だけの更新は含めない）。

## 次回の更新手順

1. 本文・リンク・構造化データ・画像の変更をレビューし、重要な更新か判断する。
2. 重要なら `sitemap.xml` と `seo/content-review.json` の `lastmod` をその実際の
   更新日（`YYYY-MM-DD`）にそろえる。同日中の更新なら日付が同じでもよい。
   軽微な変更のみなら両方の日付を維持する。
3. `change_type` を `significant` または `non-significant` とし、`reason` を
   **今回の差分に対する新しい説明**にする。軽微な変更では維持した理由を書く。
4. `python scripts/check_sitemap.py --print-content-hash` の結果を
   `content_sha256` に記録する。日時はこのコマンドで更新されない。
5. 以下を実行する。

```sh
python -m unittest discover -s tests -v
python scripts/check_sitemap.py --base origin/main
```

CIはPR（Draftを含む）とmainへのpushで実行する。本文・インラインCSS/JS、
`hero-slides.json`、`assets/`全体の追加・削除・改名・内容変更をハッシュで検知する。
保守的に見た目だけの変更も検知し、明示的なレビューで日付を維持できる。
開発用資料・CI・デプロイ設定の変更だけではハッシュは変わらない。
正規URLの一貫性、日付形式・未来日、sitemapとレビュー日付の一致も検証する。
新規ページ追加時は、1ページを前提にしたチェックとsitemapを拡張する。

機械的な検証は内容の重要性や公開履歴の事実までは判断しない。
新しいハッシュと説明を記録しただけで更新日の正しさが保証されるわけではないため、
PRレビューで差分・日付・理由を照合する。CIの必須チェック指定はリポジトリ管理者の設定が別途必要。
本workflowにはデプロイ・マージ処理はない。公開はレビュー後に判断する。
