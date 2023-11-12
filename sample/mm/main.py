from __future__ import annotations

import asyncio

from lib import (
    BuySellRatioEstimator,
    CancelOrderCommander,
    ExtendOHLCVFunction,
    ExtendOrderbookFunction,
    ExtendPositionStatusFunction,
    LimitOrderCommander,
    OHLCVLoop,
    OrderCanceler,
    OrderPricer,
    OrderRequester,
    OrderStatusLoop,
    OrderbookLoop,
    PositionStatusLoop,
    config,
)

import actchain


async def main() -> None:
    # 状態フロー
    # ポジション状態を取得・加工・配信するフロー
    flow_position_status = (
        actchain.Flow("positions")
        .add(PositionStatusLoop().as_chain("position"))
        .add(ExtendPositionStatusFunction().as_chain("position_feature"))
    )

    # 注文状態を取得・配信するフロー
    flow_order_status = actchain.Flow("orders").add(OrderStatusLoop().as_chain("order"))

    # OHLCVを取得・加工・配信するフロー
    flow_ohlcv = (
        actchain.Flow("ohlcv")
        .add(OHLCVLoop(config.ohlcv_interval).as_chain("ohlcv"))
        .add(ExtendOHLCVFunction().as_chain("ohlcv_feature"))
    )

    # 板情報を取得・加工・配信するフロー
    flow_orderbook = (
        actchain.Flow("orderbook")
        .add(OrderbookLoop().as_chain("orderbook"))
        .add(ExtendOrderbookFunction().as_chain("extend_orderbook"))
    )

    # フィーチャー作成・状態統合するフロー
    flow_feature = (
        actchain.Flow("feature")
        .add(flow_orderbook)
        .add(BuySellRatioEstimator(config.k).as_chain("buy_sell_ratio_estimator"))
        .add(actchain.AccompanyChain("position_status", flow_position_status))
        .add(actchain.AccompanyChain("order_status", flow_order_status))
        .add(actchain.AccompanyChain("ohlcv", flow_ohlcv))
    )

    # 注文フロー
    # 指値価格を計算するフロー
    flow_order_pricer = (
        actchain.Flow("order_pricer")
        .add(flow_feature)
        .add(OrderPricer(config.max_position_size).as_chain("order_pricer"))
    )

    # 指値注文を出すフロー
    flow_limit_order = (
        actchain.Flow("order")
        .add(flow_order_pricer)
        .add(
            LimitOrderCommander(
                config.order_size,
                config.max_position_size,
                config.reorder_price_diff,
            ).as_chain("order_command")
        )
        .add(
            OrderRequester().as_chain("order_request", chain_type="exclusive"),
        )
    )

    # 取消注文を出すフロー
    flow_cancel_order = (
        actchain.Flow("cancel")
        .add(flow_order_pricer)
        .add(
            CancelOrderCommander(
                config.max_position_size, config.reorder_price_diff
            ).as_chain("cancel_order_command")
        )
        .add(OrderCanceler().as_chain("cancel_order_request", chain_type="exclusive"))
    )

    # 各フローとその中を構成するchainableを実行する
    await actchain.run(
        flow_position_status,
        flow_order_status,
        flow_orderbook,
        flow_ohlcv,
        flow_feature,
        flow_order_pricer,
        flow_limit_order,
        flow_cancel_order,
        run_forever=config.run_forever,
    )


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument("-c", default="config.json", help="config file path")
    args = parser.parse_args()

    config.configure(args.c)

    asyncio.run(main())
