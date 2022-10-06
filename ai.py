# pip install websocket
# pip install websocket-client

from contextlib import closing
from websocket import create_connection
from argparse import ArgumentParser

import json

import time

money_value_map = {
    "Copper": 1,
    "Silver": 2,
    "Gold": 3,
}
deck = ["Copper"] * 7 + ["Estate"] * 3

def parse_http_endpoint(endpoint):
    ws_endpoint = "ws" + endpoint.split("http")[1]
    return ws_endpoint.split("?name=")[0]


def make_connection(parsed_endpoint, player_number):
    return create_connection(parsed_endpoint + "?name=player{}".format(player_number))
    print("start")

def action_phase(hand, treasure_count, payload, conn):
    for card in hand:
        if card in ["Market", "Village"]:
            payload["method"] = "Play"
            payload["params"] = {"card": card, "data": {}}
            print("Playing card")
            conn.send(json.dumps(payload))
            response = conn.recv()
            response_parsed = json.loads(response)
            print(response_parsed)
            hand = response_parsed["result"]["hand"]
            treasure_count = response_parsed["result"]["treasure"]
            return action_phase(hand, treasure_count, payload, conn)
    return treasure_count, hand  

def play_turn(response, payload, conn):
    params = response["params"]
    money_count = 0
    # Action Phase
    money_count, hand = action_phase(params["hand"], money_count, payload, conn)
    # Buy Phase
    for card in hand:
        if card in ["Copper", "Silver", "Gold"]:
            money_count += money_value_map[card]
            payload["method"] = "Play"
            payload["params"] = {"card": card, "data": {}}
            #print("Playing card")
            conn.send(json.dumps(payload))
            response = conn.recv()
            #print(response)
    return money_count

def find_cards_to_buy(money_count):
    card_to_buy = "Province"
    if money_count < 8:
        card_to_buy = "Gold"
    if money_count < 6:
        card_to_buy = "Silver"
    if money_count < 5:
        card_to_buy = "Silver"
    if money_count < 3:
        card_to_buy = "Copper"
    return [card_to_buy]


def run_server(conn):
    global deck
    turn_count = 0
    while(True):
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
        }
        response = conn.recv()
        print(response)
        response_parsed = json.loads(response)
        if response_parsed.get("method") == None:
            continue
        if response_parsed["method"] == "StartGame":
            payload_id = response_parsed["id"]
            payload["id"] = payload_id
            payload["result"] = {}
            conn.send(json.dumps(payload))
        elif response_parsed["method"] == "StartTurn":
            turn_count += 1
            #print(deck)
            money_count = play_turn(response_parsed, payload, conn)
            cards_to_buy = find_cards_to_buy(money_count)
            #print(cards_to_buy)

            for card in cards_to_buy:
                payload["method"] = "Buy"
                payload["params"] = {"card": card}
                #print("Buying card")
                conn.send(json.dumps(payload))
                deck += [card]
            payload["method"] = "EndTurn"
            payload.pop("params")

            #print("ending turn")
            #print(payload)
            conn.send(json.dumps(payload))
        elif response_parsed["method"] == "GameOver":
            break 
    print("TURN COUNT:{}".format(turn_count))
    conn.close()


def main(args):
    parser = ArgumentParser()
    parser.add_argument("--http_endpoint", action="store", help="Doninai Endpoint with or without default name.", type=str)
    parser.add_argument("--player", action="store", help="Doninai player number", type=str)
    args = parser.parse_args(args)
    args_dict = vars(args)
    endpoint = parse_http_endpoint(args_dict["http_endpoint"])
    connection = make_connection(endpoint, args_dict["player"])
    run_server(connection)

if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
