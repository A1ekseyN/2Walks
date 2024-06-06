import asyncio
import websockets
import json
from datetime import datetime, timedelta
from collections import deque

async def monitor_prices():
    url = "wss://fstream.binance.com/ws/btcusdt@aggTrade"

    # Variables to track total buy and sell volumes
    total_buy_volume = 0
    total_sell_volume = 0

    # Deque to store net volume changes with timestamps for the last 5 and 1 minutes
    net_volume_5_min = deque()
    net_volume_1_min = deque()

    async with websockets.connect(url) as websocket:
        while True:
            response = await websocket.recv()
            data = json.loads(response)

            symbol = data['s']
            price = data['p']
            quantity = float(data['q'])
            trade_time_ms = int(data['T'])
            trade_time = datetime.fromtimestamp(trade_time_ms / 1000.0)
            trade_type = "SELL" if data['m'] else "BUY"

            # Update total buy or sell volume based on trade type
            if trade_type == "BUY":
                total_buy_volume += quantity
                net_volume_change = quantity  # Positive for buy
            else:
                total_sell_volume += quantity
                net_volume_change = -quantity  # Negative for sell

            net_volume = total_buy_volume - total_sell_volume
            net_volume = round(net_volume, 4)

            # Append the new trade to the deques
            net_volume_5_min.append((trade_time, net_volume_change))
            net_volume_1_min.append((trade_time, net_volume_change))

            # Remove outdated entries from the deques
            current_time = datetime.now()
            while net_volume_5_min and current_time - net_volume_5_min[0][0] > timedelta(minutes=5):
                net_volume_5_min.popleft()
            while net_volume_1_min and current_time - net_volume_1_min[0][0] > timedelta(minutes=1):
                net_volume_1_min.popleft()

            # Calculate net volume for the last 5 and 1 minutes
            net_volume_last_5_min = sum(change for time, change in net_volume_5_min)
            net_volume_last_5_min = round(net_volume_last_5_min, 4)
            net_volume_last_1_min = sum(change for time, change in net_volume_1_min)
            net_volume_last_1_min = round(net_volume_last_1_min, 4)

            print(f"{trade_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} - {symbol}, Price: {price} $, Quantity: {quantity}, "
                  f"Trade Type: {trade_type}, Net Volume: {net_volume} BTC, "
                  f"Net Volume 1 min: {net_volume_last_1_min} BTC, "
                  f"Net Volume 5 min: {net_volume_last_5_min} BTC")

if __name__ == "__main__":
    asyncio.run(monitor_prices())
