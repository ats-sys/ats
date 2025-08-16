import time
import shutil
import logging
import random
import json
import traceback
import yaml

import sys
import os

# Add the root folder to the Python path
root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_folder)

from ats.exchanges.exchanges.hyperliquid_spot.exchange import Exchange
from ats.utils.time.timer import Timer
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.candle import Candle

# Load configuration
with open('ats/tests/configs/hyperliquid_test_exchange_config.yaml', 'r') as file:
    # Load the YAML content into a dictionary
    config = yaml.safe_load(file)['exchange']['config']

exchange = Exchange(config=config)
exchange.connect()

testing_step = 1
candle_counter = 0
current_asset_price = None


def print_testing_step(step_name):
    global testing_step

    text = f'TESTING STEP {testing_step}: {step_name}'

    terminal_width, _ = shutil.get_terminal_size()

    decoration_length = (terminal_width - len(text)) // 2

    decoration = '-' * decoration_length

    print('\n' + decoration + text + decoration)

    testing_step += 1


def test_check_wallet_balance():
    print_testing_step('Fetching wallet balance.')
    while True:
        wallet_balance = exchange.get_wallet_balance()
        print(wallet_balance)
        if wallet_balance is not None:
            print('Received wallet balance.')
            print('Test completed\n')
            break
        time.sleep(1)


def test_simple_market_order():
    print_testing_step('Submitting 2 MARKET orders (Buy and Sell)')
    order_1 = Order(order_side='BUY', order_type='MARKET',
                    size=0.0001,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    order_2 = Order(order_side='SELL', order_type='MARKET',
                    size=0.0001,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    print('Order 1 starting state :', order_1.order_status)
    print('Order 2 starting state :', order_2.order_status)

    try:
        exchange.submit_order(order_1)
    except Exception as e:
        print(e)
        traceback.print_exc()

    try:
        exchange.submit_order(order_2)
    except Exception as e:
        print(e)
        traceback.print_exc()

    print('Sleeping 3 sec till orders are completed.')
    time.sleep(3)
    exchange.get_order(order_1.order_id)
    exchange.get_order(order_2.order_id)

    print('Order 1 end state :', order_1.order_status)
    print('Order 2 end state :', order_2.order_status)

    if order_1.order_status != 'FILLED':
        raise Exception(f'Order 1 is not FILLED.')

    if order_2.order_status != 'FILLED':
        raise Exception(f'Order 2 is not FILLED.')

    print('Test completed\n')


def test_submitting_limit_orders_and_cancelling():
    print_testing_step('A LIMIT order pair is submitted and it is cancelled.')

    global current_asset_price

    current_asset_price = None

    def update_asset_price(candle):
        global current_asset_price
        current_asset_price = candle.close

    exchange.on_candle(on_data_callable=update_asset_price)
    print(f'Waiting for current close price of {config["symbol"]["base"]}')

    while True:
        if current_asset_price is not None:
            break
        time.sleep(1)

    print(f'Got the current close price {current_asset_price}.')

    # Create buy order 1% below current price
    order_1 = Order(order_side='BUY', order_type='LIMIT',
                    size=0.0001,
                    price=round(current_asset_price - current_asset_price/100, 0),
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    # Create sell order 1% above current price
    order_2 = Order(order_side='SELL', order_type='LIMIT',
                    size=0.0001,
                    price=round(current_asset_price + current_asset_price/100, 0),
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    exchange.submit_order(order_1)
    exchange.submit_order(order_2)

    # Wait a bit to ensure orders are submitted
    time.sleep(5)
    exchange.get_order(order_1.order_id)
    exchange.get_order(order_2.order_id)
    time.sleep(5)

    exchange.cancel_order(order_1)
    exchange.cancel_order(order_2)

    time.sleep(5)
    exchange.get_order(order_1.order_id)
    exchange.get_order(order_2.order_id)

    print('Waiting 10 secs till order cancellation is done.')
    time.sleep(10)

    if order_1.order_status != OrderStatus.CANCELED:
        raise Exception(f'Order 1 is not CANCELED.')

    if order_2.order_status != OrderStatus.CANCELED:
        raise Exception(f'Order 2 is not CANCELED.')

    print('Test completed\n')


def test_on_candle_callback():
    print_testing_step('Testing "on_candle" callback for 3 candles.')
    global candle_counter
    def on_candle_counter(candle):
        global candle_counter

        if isinstance(candle, Candle):
            expected_symbol = config['symbol']['base'] + config['symbol']['quote']
            if candle.symbol != expected_symbol:
                raise Exception(f'Candle symbol does not match the configured symbol. Received: {candle.symbol}, expected: {expected_symbol}')

            candle_counter += 1
            print("Counter updated", candle_counter, "for candle:", candle)
        else:
            print('WARN: Data received but not a candle object.')

    exchange.on_candle(on_data_callable=on_candle_counter)

    while True:
        if candle_counter > 3:
            break
        time.sleep(1)

    exchange.remove_on_candle_callback()
    print('Test completed\n')


# Run tests
test_check_wallet_balance()
#
test_simple_market_order()
test_submitting_limit_orders_and_cancelling()
test_on_candle_callback()
#
exchange.disconnect()
