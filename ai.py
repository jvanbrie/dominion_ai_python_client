from argparse import ArgumentParser
import json
from websocket import create_connection

print_logs = False
def log(*args):
    if print_logs:
        print(args)

ordered_playable_cards = {
    "Mine" : 1,
    "Smithy" : 1,
    "Militia" : 2
}

class State(object):
    def __init__(self) -> None:
        self.hand = []
        self.discard = 0
        self.deck = ["Copper"] * 7 + ["Estate"] * 3
        self.supply = {}
        self.buys = 1
        self.actions = 1
        self.treasure = 0
        self.payload = None
        self.conn = None

    def __repr__(self) -> str:
        return "${} | {} actions | {} buys | {} discard | avg_draw_wo_action: {} | deck: {} | hand: {} ".format(
            self.treasure, 
            self.actions, 
            self.buys, 
            self.discard, 
            self.average_value_draw_without_action(),
            self.deck, 
            self.hand, 
            )
    def average_value_draw_without_action(self) -> int:
        total_value = 0
        for card in self.deck:
            if card == "Gold":
                total_value += 3
            if card == "Silver":
                total_value += 2
            if card == "Copper":
                total_value += 1
        return total_value / len(self.deck)
            

class Strategy(object):
    def find_cards_to_buy(self, state: State) -> list[str]:
        raise Exception("Not Implemented")

class StrategyOne(Strategy):
    def find_cards_to_buy(self, state: State) -> list[str]:
        card_to_buy = "Province"
        if state.treasure < 8:
            card_to_buy = "Gold"
        if state.treasure < 6:
            if len(list(filter(lambda x: x == "Smithy", state.deck))) < 1:
                card_to_buy = "Smithy"
            else:
                card_to_buy = "Silver"
        if state.treasure < 4:
            card_to_buy = "Silver"
        if state.treasure < 3:
            return []
        return [card_to_buy]

class StrategyTwo(Strategy):
    def find_cards_to_buy(self, state: State) -> list[str]:
        card_to_buy = "Province"
        if state.treasure < 8:
            card_to_buy = "Gold"
        if state.treasure < 6:
            if state.deck.count("Mine") < 1:
                card_to_buy = "Mine"
        if state.treasure < 5:
            card_to_buy = "Silver"
        if state.treasure < 3:
            return []
        return [card_to_buy]

def action_phase(state):
    playable_prioritize = [card for card in state.hand if card in ["Market", "Village"]]
    for card in playable_prioritize:
        if state.actions < 1:
            break
        play_card(card, state)
    playable = sorted([card for card in state.hand if card in ordered_playable_cards.keys()], key=(lambda x : ordered_playable_cards[x]))
    for card in playable:
        if state.actions < 1:
            break
        if (card == "Mine" and len(list(filter(lambda x: (x == "Copper") or (x == "Silver"), state.hand))) == 0):
            continue
        play_card(card, state)


def buy_phase(state, strategy):
    playable = [card for card in state.hand if card in [
        "Copper", "Silver", "Gold"]]
    for card in playable:
        play_card(card, state)
    for card in strategy.find_cards_to_buy(state):
        if state.supply[card] > 0:
            buy_card(card, state)

def play_card(card, state):
    state.payload["method"] = "Play"
    if (card == "Mine"):
        if "Silver" in state.hand:
            card_data = {"trash": "Silver", "gain": "Gold"}
        else:
            card_data = {"trash": "Copper", "gain": "Silver"}
    else:
        card_data = {}
    state.payload["params"] = {"card": card, "data": card_data}
    log("Playing", card)
    state.conn.send(json.dumps(state.payload))
    action_response(state)


def buy_card(card, state):
    state.deck += [card]
    state.payload["method"] = "Buy"
    state.payload["params"] = {"card": card}
    log("Buying", card)
    state.conn.send(json.dumps(state.payload))
    action_response(state)


def action_response(state):
    response = json.loads(state.conn.recv())
    if (error := response.get("error")) is not None:
        print("Fatal error:", error)
        exit(1)
    elif (result := response.get("result")) is not None:
        parse_response(state, result)
        log(state)

def parse_response(state, response):
    state.hand = response["hand"]
    state.discard = response["discard"]
    state.supply = response["supply"]
    if "buys" in response:
        state.buys = response["buys"]
    if "actions" in response:
        state.actions = response["actions"]
    if "treasure" in response:
        state.treasure = response["treasure"]


def end_turn(state):
    state.payload["method"] = "EndTurn"
    if "params" in state.payload:
        state.payload.pop("params")
    state.conn.send(json.dumps(state.payload))
    if state.supply.get("Province", 0) != 0:
        response = json.loads(state.conn.recv())
        parse_response(state, response["result"])

def handle_attack(state, request):
    default_card_value = 1
    card_to_value_in_hand = {
        "Estate" : 0,
        "Duchy": 0,
        "Province": 0,
        "Copper": 1,
        "Silver": 2,
        "Gold": 3,
        "Market": 2,
        "Militia": 2,
    }
    if request["card"] == "Militia":
        if len(state.hand) > 3:
            curr_hand = state.hand
            curr_hand.sort(key = lambda x: card_to_value_in_hand.get(x, default_card_value))
            cards_to_discard = curr_hand[:2]
            state.payload["result"]["data"] = cards_to_discard
            state.hand = curr_hand[2:]
            state.conn.send(json.dumps(state.payload))
        else:
            state.payload["result"]["data"] = []
            state.conn.send(json.dumps(state.payload))
    else:
        print("Unhandled Attack")
        print(request)


def run_server(conn, player_number, number_of_rounds):
    state = State()
    player_one_wins = 0
    player_two_wins = 0
    ties = 0
    if player_number == 1:
        strategy = StrategyOne()
    else:
        strategy = StrategyTwo()
    while True:
        payload = {
            "jsonrpc": "2.0",
            "id": 0,
        }
        response = json.loads(conn.recv())

        if (method := response.get("method")) is None:
            continue
        if method == "StartGame":
            payload_id = response["id"]
            payload["id"] = payload_id
            payload["result"] = {}
            conn.send(json.dumps(payload))
        elif method == "FatalError":
            print("Fatal error:", response["message"])
            exit(1)
        elif method == "StartTurn":
            parse_response(state, response["params"])
            log(state)
            state.payload = payload
            state.conn = conn
            action_phase(state)
            buy_phase(state, strategy)
            end_turn(state)
        elif method == "Attack":
            payload_id = response["id"]
            payload["id"] = payload_id
            payload["result"] = {}
            state.payload = payload
            handle_attack(state, response["params"])
        elif method == "GameOver":
            print(response["params"])
            p1_score = response["params"]["scores"]["player1"] 
            p2_score = response["params"]["scores"]["player2"]
            if p1_score > p2_score:
                 player_one_wins += 1
            elif p1_score < p2_score:
                player_two_wins += 1
            else:
                 ties += 1
            number_of_rounds -= 1
            if number_of_rounds <= 0:
                payload_id = response["id"]
                payload["id"] = payload_id
                payload["result"] = {"rematch": False}
                conn.send(json.dumps(payload))
                break
            else:
                payload_id = response["id"]
                payload["id"] = payload_id
                payload["result"] = {"rematch": True}
                conn.send(json.dumps(payload))
                state = State()
        else:
            print(response)
    print("Player 1 wins: {} | Ties: {} | Player 2 wins: {}".format(
        player_one_wins, ties, player_two_wins
        ))
    conn.close()


def main(args):
    parser = ArgumentParser()
    parser.add_argument("--http_endpoint", action="store",
                        help="Dominai Endpoint with or without default name.", type=str)
    parser.add_argument("--player", action="store",
                        help="Dominai player number", type=int)
    parser.add_argument("--number_of_rounds", action="store",
                    help="Number of games to play", type=int, default=1)
    args = parser.parse_args(args)
    args_dict = vars(args)

    def parse_http_endpoint(endpoint):
        ws_endpoint = "ws" + endpoint.split("http")[1]
        return ws_endpoint.split("?name=")[0]

    def make_connection(parsed_endpoint, player_number):
        return create_connection(parsed_endpoint + "?name=player{}".format(player_number))

    endpoint = parse_http_endpoint(args_dict["http_endpoint"])
    connection = make_connection(endpoint, args_dict["player"])
    run_server(connection, args_dict["player"], args_dict["number_of_rounds"])


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
