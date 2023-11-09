# bitflyerでマーケットメイク

## 準備

python 3.11.0 or higherを準備。

`pybotters-apis.json`を用意して、`main.py`と同じディレクトリに置く。

```json
{
  "bitflyer": [
    "YOUR_API_KEY",
    "YOUR_API_SECRET"
  ]
}
```

config.json.templateをコピーしてconfig.jsonを作る。

```bash
cp config.json.template config.json
```

パラメーター一覧。適宜いじる。

```python
# pybotters用のapiキーが記載されたjsonファイルのパス
pybotters_apis: str = "pybotters-apis.json"
# 注文サイズ
order_size: float = 0.01
# 最大ポジションサイズ
max_position_size: float = 0.02
# ターゲットスプレッドの何%離れたら再注文するか
reorder_price_diff: float = 0.2
# 買売比率算出パラメーター（feature.BuySellRatioEstimatorを参照）
k: int = 20
# ローソク足のインターバル
ohlcv_interval: TInterval = "5m"
# apiリミット超過時の待機時間
sleep_at_api_limit: int = 300
# 注文後の待機時間
order_interval: int = 3
# 永続化するかどうか
run_forever: bool = True
```

ライブラリをインストール。

```bash
pip loguru better-exceptions install httpx git+https://github.com/ko0hi/pybotters-wrapper
```

実行。


```bash
PYTHONPATH=../../ python main.py -c config.json
```

## アルゴ

仲値から一定距離離れたところに買い注文と売り注文を出し続ける。

仲直はポジションと市場の買売圧に応じて調整する。

距離はボラティリティを参照する。

[杉原論文](https://www.imes.boj.or.jp/research/papers/japanese/kk31-1-8.pdf)で紹介されてるやつを参考にした。



