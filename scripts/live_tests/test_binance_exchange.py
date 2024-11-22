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

from binance.spot import Spot
from binance.websocket.spot.websocket_api import SpotWebsocketAPIClient
from binance.websocket.spot.websocket_stream import SpotWebsocketStreamClient
from ats.exchanges.exchanges.binance_spot.exchange import Exchange
from ats.utils.time.timer import Timer
from ats.exchanges.data_classes.order import Order, OrderStatus
from ats.exchanges.data_classes.candle import Candle


with open('tests/configs/binance_test_exchange_config.yaml', 'r') as file:
    # Load the YAML content into a dictionary
    config = yaml.safe_load(file)['exchange']['config']

exchange = Exchange(config=config)

exchange.connect()

testing_step = 1
candle_counter = 0
current_asset_price = None

smallest_price = float(exchange._Exchange__binance_price_filter['tickSize'])
smallest_size = float(exchange._Exchange__binance_size_filter['stepSize'])
smallest_notional_amount = float(exchange._Exchange__binance_notional_filter['minNotional'])


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
        if wallet_balance is not None:
            print('Received wallet balance.')
            print('Test completed\n')
            break
        time.sleep(1)


def test_simple_market_order():
    print_testing_step('Submitting 2 MARKET orders (Buy and Sell)')
    order_1 = Order(order_side='BUY', order_type='MARKET',
                    size=0.001,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    order_2 = Order(order_side='SELL', order_type='MARKET',
                    size=0.001,
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

    print('Order 1 end state :', order_1.order_status)
    print('Order 2 end state :', order_2.order_status)

    if order_1.order_status != 'FILLED':
        raise Exception(f'Order 1 is not FILLED.')

    if order_2.order_status != 'FILLED':
        raise Exception(f'Order 2 is not FILLED.')

    print('Test completed\n')


def test_submitting_large_market_order():
    print_testing_step('Large MARKET order submission. Expecting a rejection.')
    order_1 = Order(order_side='BUY', order_type='MARKET', size=1000000,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    try:
        exchange.submit_order(order_1)
        raise Exception('Large order is submitted without error. An error from the exchange is expected')
    except Exception as e:
        if order_1.order_status != 'REJECTED':
            raise Exception(f'Large order is rejected by exchange. Expected "REJECTED" state but received {order_1.order_status}')
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

    order_1 = Order(order_side='BUY', order_type='LIMIT',
                    size=smallest_notional_amount / (current_asset_price - current_asset_price/100) * 2,
                    price=current_asset_price - current_asset_price/100,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    order_2 = Order(order_side='SELL', order_type='LIMIT',
                    size=smallest_notional_amount / (current_asset_price + current_asset_price/100) * 2,
                    price=current_asset_price + current_asset_price/100,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    exchange.submit_order(order_1)
    exchange.submit_order(order_2)

    exchange.cancel_order(order_1)
    exchange.cancel_order(order_2)

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
                raise Exception(f'Candle symbol does not match the configured symbol. Recieved: {candle.symbol}, expected: {expected_symbol}')

            candle_counter += 1
        else:
            print('WARN: Data received but not a candle object.')

    exchange.on_candle(on_data_callable=on_candle_counter)

    while True:
        if candle_counter > 3:
            break
        time.sleep(1)

    exchange.remove_on_candle_callback()
    print('Test completed\n')

def test_limit_order_pair():
    print_testing_step('A LIMIT order pair is submitted and waited for the completion')

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

    price_multiple = 500

    order_1 = Order(order_side='BUY', order_type='LIMIT',
                    size=smallest_notional_amount / (current_asset_price - smallest_price * price_multiple) * 2,
                    price=current_asset_price - smallest_price * price_multiple,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    order_2 = Order(order_side='SELL', order_type='LIMIT',
                    size=smallest_notional_amount / (current_asset_price + smallest_price * price_multiple) * 2,
                    price=current_asset_price + smallest_price * price_multiple,
                    base_symbol=config['symbol']['base'],
                    quote_symbol=config['symbol']['quote']
                    )

    print(f'Order 1 was submitted at {order_1.price}')
    print(f'Order 2 was submitted at {order_2.price}')

    exchange.submit_order(order_1)
    exchange.submit_order(order_2)

    while True:
        if order_1.order_status == OrderStatus.FILLED and order_2.order_status == OrderStatus.FILLED:
            break
        time.sleep(1)

    print('Test completed\n')




test_check_wallet_balance()
test_submitting_large_market_order()
test_submitting_limit_orders_and_cancelling()
test_simple_market_order()
test_on_candle_callback()
test_limit_order_pair()

exchange.disconnect()