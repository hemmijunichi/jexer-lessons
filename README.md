# jexer-lessons

ジェクサー各店の公開グループレッスン時間割から BODY COMBAT / BODY ATTACK / UBOUND の枠を毎月集めます。

www.jexer.jp は GitHub Actions のサーバーからの接続を受け付けないため、毎月1日 9:00 に手元の Windows PC のタスクスケジューラ（タスク名 `jexer-lessons`）が `run_monthly.ps1` を実行し、結果をこのリポジトリに push します。PC が切れていた場合は次に起動したときに実行されます。

## 出力

- `data/latest.txt` … 最新の今月分
- `data/YYYYMM.txt` … 月ごとの保存
- `data/next.txt` … 翌月分（公開されていれば）
- `data/stores.json` … 店舗ごとの shop番号・休館曜日・件数・取得日時
- `data/warnings.txt` … 店舗名の不一致・件数0の店舗

1行1枠: `曜日|開始|終了|C/A/U|プログラム名|店舗|スタジオ|担当|フラグ|備考`

フラグ: w=予約アイコンあり x=なし d=暗闇 v=VR y=有料 n=NEW b=初心者

同じ枠が複数のスタジオ列に載っている場合（大宮のアリーナ①・②など）は1行にまとめ、スタジオ名を「・」でつなぎます。

## 手元で実行

```
pip install -r requirements.txt
python scrape.py          # 今月分
python scrape.py --next   # 翌月分
```
