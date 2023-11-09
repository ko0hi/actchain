from __future__ import annotations

import json
import os
from dataclasses import dataclass

import actchain

from .ohlcv import TInterval


@dataclass
class Config(actchain.State):
    """
    actchain.Stateはシングルトンクラス。
    コンフィグのようにグローバルにアクセスしたい変数を保管しておくのに便利。
    ただし何でもかんでもactchain.Stateで宣言すると管理が難しくなるので使いすぎ注意。
    """

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

    @classmethod
    def configure(cls, filepath: str) -> Config:
        c = cls()
        with open(filepath) as f:
            params = json.load(f)
        for k, v in params.items():
            setattr(c, k, v)
        os.environ["PYBOTTERS_APIS"] = c.pybotters_apis
        cls.validate()
        return c

    @classmethod
    def validate(cls) -> None:
        assert 0 < cls().reorder_price_diff < 1, "reorder_price_diff must be in (0, 1)"


config = Config()
