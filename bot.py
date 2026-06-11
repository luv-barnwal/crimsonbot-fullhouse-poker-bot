"""
╔══════════════════════════════════════════════════════════════╗
║         FULLHOUSE HACKATHON — BOT TEMPLATE v1.0             ║
║         No-Limit Texas Hold'em, 6-max                        ║
╚══════════════════════════════════════════════════════════════╝

RULES:
  - Implement the decide() function below. That's it.
  - You may import any stdlib module and any library in requirements.txt
  - You have 2 seconds to return an action or you auto-fold
  - If your function crashes, it auto-folds for that hand

NOT ALLOWED (will DQ your bot):
  - External API calls: no Claude/OpenAI/Anthropic/Google/any HTTP. Network is
    blocked at the container level; trying anyway is a DQ.
  - File writes during gameplay; data/ is read-only and only at import time.
  - subprocess / os.system / shell commands.
  - Threading or async tricks to dodge the 2s/action signal timer.
  - Reflection: __import__('socket'), getattr(__builtins__, 'open'),
    eval(), exec(), compile() — all flagged by the validator.
  - Collusion between bots you've registered with friends — bots must play
    independently; coordinated soft-play or chip-dumping = both DQ'd.
  - Reading other bots' code or hole cards (you can't anyway, but trying = DQ).

OPTIONAL DATA FILES (NEW):
  Submit a .zip archive containing:
    bot.py        (this file, required at root)
    data/         (optional directory with .npz, .pkl, .bin, etc.)

  At module-import time only, you can read from a sibling 'data/' directory:

      import os
      DATA_DIR = os.environ.get("BOT_DATA_DIR",
                                os.path.join(os.path.dirname(__file__), "data"))
      with open(os.path.join(DATA_DIR, "blueprint.npz"), "rb") as f:
          BLUEPRINT = ...load(f)

  Limits:
    - Total submission (bot.py + data/) <= 250 MB
    - data/ alone <= 200 MB
    - bot.py <= 5 MB
    - File access during decide() is blocked at the OS level

CARD FORMAT:
  Cards are strings like "As" (Ace of spades), "Td" (Ten of diamonds)
  Ranks: 2 3 4 5 6 7 8 9 T J Q K A
  Suits: s (spades) h (hearts) d (diamonds) c (clubs)

RETURN FORMAT:
  {"action": "fold"}
  {"action": "check"}          # only valid when amount_owed == 0
  {"action": "call"}
  {"action": "raise", "amount": 1200}   # amount = TOTAL bet, not raise-by
  {"action": "all_in"}

  Invalid actions default to fold. Raises below min_raise_to are snapped up.
"""

# ── You may add imports here ──────────────────────────────────────────────────
import random
import json
import os
import eval7
# ─────────────────────────────────────────────────────────────────────────────

BOT_NAME = "CrimsonBot"          # Show name on the leaderboard
BOT_AVATAR = "robot_1"      # Chosen in the portal, not here

DATA_DIR = os.environ.get("BOT_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
RANKS = "23456789TJQKA"

with open(os.path.join(DATA_DIR, "preflop_equity.json"), "r") as f:
    PREFLOP_EQUITY = json.load(f)

opponent_stats = {}
hand_state = {}

def get_preflop_equity(cards):
    first_rank, second_rank = cards[0][0], cards[1][0]
    if first_rank == second_rank:
      return PREFLOP_EQUITY[first_rank+second_rank]
    if RANKS.index(first_rank) < RANKS.index(second_rank):
      first_rank, second_rank = second_rank, first_rank
    if cards[0][1] == cards[1][1]:
      return PREFLOP_EQUITY[first_rank+second_rank+"s"]
    return PREFLOP_EQUITY[first_rank+second_rank+"o"]

def get_raise_frequency(seat):
    if seat not in opponent_stats or opponent_stats[seat]["actions"] == 0:
        return 0.2  # default prior, assume 20% raise frequency
    stats = opponent_stats[seat]
    return (stats["raises"] + 4) / (stats["actions"] + 20)


def estimate_equity(hole_cards, community_cards, players, my_seat, num_simulations=300):
    hole = [eval7.Card(c) for c in hole_cards]
    board = [eval7.Card(c) for c in community_cards]

    deck = eval7.Deck()
    deck.cards = [c for c in deck.cards if c not in hole + board]

    active_opponents = [p for p in players if not p["is_folded"] and p["seat"] != my_seat]
    num_opponents = max(1, len(active_opponents))

    wins = 0
    for _ in range(num_simulations):
      deck.shuffle()
      opponent_hands = [deck.cards[i*2: (i+1)*2] for i in range(num_opponents)]
      remaining_start = num_opponents * 2
      remaining_board = deck.cards[remaining_start: remaining_start + (5 - len(board))]
      full_board = board + remaining_board

      my_score = eval7.evaluate(hole + full_board)
      best_opp = max(eval7.evaluate(opp + full_board) for opp in opponent_hands)

      if my_score > best_opp:
        wins += 1
      elif my_score == best_opp:
        wins += 0.5
    return wins / num_simulations

def board_is_scary(community_cards):
    if len(community_cards) < 3:
        return False
    suits = [c[1] for c in community_cards]
    flush_possible = max(suits.count(s) for s in suits) >= 3
    ranks_numeric = sorted([RANKS.index(c[0]) for c in community_cards])
    straight_possible = (ranks_numeric[-1] - ranks_numeric[0] <= 2 and 
                        len(set(ranks_numeric)) == len(ranks_numeric))
    paired_board = len(ranks_numeric) != len(set(ranks_numeric))
    return flush_possible or straight_possible or paired_board

def decide(game_state: dict) -> dict:
    """
    Called once per action. Must return within 2 seconds.

    game_state keys:
      hand_id          str   — unique hand identifier
      street           str   — "preflop" | "flop" | "turn" | "river"
      seat_to_act      int   — your seat number (0-5)
      pot              int   — total chips in pot
      community_cards  list  — e.g. ["As", "Kd", "7h"] (empty preflop)
      current_bet      int   — highest bet on this street
      min_raise_to     int   — minimum legal raise total
      amount_owed      int   — chips you need to put in to call (0 = free check)
      can_check        bool  — True when amount_owed == 0
      your_cards       list  — your two hole cards, e.g. ["Ah", "Kh"]
      your_stack       int   — your remaining chips
      your_bet_this_street int — chips you've already put in this street
      players          list  — public info on all seats (see below)
      action_log       list  — all actions so far this hand

    players[i] keys (public info only, no hole cards):
      seat, bot_id, stack, state, is_folded, is_all_in, bet_this_street, hole_cards
      `state` is a string: "active" | "folded" | "all_in" | "busted"
      `hole_cards` is always None for opponents (only revealed at showdown)
    """

    # ── Your strategy goes here ───────────────────────────────────────────────

    my_cards = game_state["your_cards"]
    street = game_state["street"]
    amount_owed = game_state["amount_owed"]
    pot = game_state["pot"]
    my_stack = game_state["your_stack"]
    can_check = game_state["can_check"]
    min_raise_to = game_state["min_raise_to"]
    my_seat = game_state["seat_to_act"]
    players = game_state["players"]
    community_cards = game_state["community_cards"]
    action_log = game_state["action_log"]
    my_bet_this_street = game_state["your_bet_this_street"]

    position = my_seat / 5  # 0.0 early, 1.0 late

    # count active opponents
    active_opponents = len([p for p in players 
                           if not p["is_folded"] 
                           and p["state"] != "busted"
                           and p["seat"] != my_seat])

    # update opponent stats
    last_processed = opponent_stats.get("_last_processed", 0)
    for entry in action_log[last_processed:]:
        seat = entry.get("seat")
        action = entry.get("action")
        if seat is None or seat == my_seat:
            continue
        if action in ("small_blind", "big_blind"):
            continue
        if seat not in opponent_stats:
            opponent_stats[seat] = {"raises": 0, "actions": 0}
        if action in ("raise", "all_in"):
            opponent_stats[seat]["raises"] += 1
        if action in ("raise", "call", "fold", "check", "all_in"):
            opponent_stats[seat]["actions"] += 1
    opponent_stats["_last_processed"] = len(action_log)

    # blind detection
    sb_seat = None
    bb_seat = None
    for entry in action_log:
        if entry.get("action") == "small_blind":
            sb_seat = entry.get("seat")
        if entry.get("action") == "big_blind":
            bb_seat = entry.get("seat")
    am_bb = (my_seat == bb_seat)
    am_sb = (my_seat == sb_seat)

    # aggressor detection
    aggressor_seat = None
    for entry in reversed(action_log):
        if entry.get("action") in ("raise", "all_in") and entry.get("seat") != my_seat:
            aggressor_seat = entry.get("seat")
            break
    aggressor_rf = get_raise_frequency(aggressor_seat) if aggressor_seat is not None else 0.2
    stack_ratio = my_stack / 10000

    # ── PREFLOP ──────────────────────────────────────────────────────────────
    if street == "preflop":
        equity = get_preflop_equity(my_cards)

        # position-based threshold
        if am_bb:
            threshold = 0.58
        elif am_sb:
            threshold = 0.63
        else:
            threshold = 0.67 - (position * 0.10)  # 0.65, 0.55

        # tighten vs aggressive raisers
        if aggressor_rf > 0.4:
            threshold += 0.04

        preflop_raises = [
            e for e in action_log
            if e.get('action') in ('raise', 'all_in')
            and e.get('seat') != my_seat
        ]
        num_prior_raises = len(preflop_raises)
        if stack_ratio < 0.2 and amount_owed > 0 and equity < 0.75:
            return {"action": "fold"}
        
        if num_prior_raises >= 3 and equity < 0.75:
            return {"action": "fold"}
        elif num_prior_raises >= 2 and equity < 0.68:
            return {"action": "fold"}
        elif num_prior_raises >= 1 and equity < 0.58:
            return {"action": "fold"}

        i_already_raised_preflop = hand_state.get(game_state["hand_id"], {}).get("raised_preflop", False)
        if i_already_raised_preflop and num_prior_raises >= 1:
            if equity < 0.68:
                return {"action": "fold"}
            return {"action": "call"}

        if equity > threshold:
            hand_state[game_state["hand_id"]] = {"raised_preflop": True}
            raise_amount = max(min_raise_to, 300)
            raise_amount = min(raise_amount, int(my_stack * 0.3))
            return {"action": "raise", "amount": raise_amount}

        # call if pot odds justify it
        if amount_owed > 0:
            pot_odds = amount_owed / (pot + amount_owed)
            if equity > pot_odds + 0.04:
                return {"action": "call"}

        if can_check:
            return {"action": "check"}
        return {"action": "fold"}

    # ── POSTFLOP ─────────────────────────────────────────────────────────────
    else:
        num_sims = 500 if len(community_cards) == 5 else 300
        equity = estimate_equity(my_cards, community_cards, players, my_seat, num_sims)

        # scale thresholds for number of opponents
        opponent_penalty = (active_opponents - 1) * 0.05
        scary = board_is_scary(community_cards)

        total_invested_this_hand = sum(
            a.get('amount', 0) for a in action_log if a.get('seat') == my_seat
        )
        starting_stack = my_stack + total_invested_this_hand
        hand_investment_cap = min(starting_stack, 10000) * 0.25

        # fold/check when too many raises in hand
        total_raises_this_hand = sum(
            1 for e in action_log
            if e.get('action') in ('raise', 'all_in')
        )
        my_raises_this_hand = sum(
            1 for e in action_log
            if e.get('action') in ('raise', 'all_in')
            and e.get('seat') == my_seat
        )

        if total_invested_this_hand < hand_investment_cap:
            if total_raises_this_hand >= 6 and equity < 0.80:
                if amount_owed > 0:
                    return {"action": "fold"}
                return {"action": "check"}
            if my_raises_this_hand >= 3 and equity < 0.75:
                if amount_owed > 0:
                    return {"action": "fold"}
                return {"action": "check"}
        # if total_invested_this_hand > hand_investment_cap and equity < 0.65:
        #     return {"action": "fold"}
        
        if total_invested_this_hand > hand_investment_cap:
            required_equity = 0.65 + (total_raises_this_hand * 0.02)
            required_equity = min(required_equity, 0.80)  # cap at 0.80
            if equity < required_equity and amount_owed > 0:
                return {"action": "fold"}

        if stack_ratio < 0.2:
            call_threshold = 0.65
            bet_threshold = 0.70
            bluff_freq = 0.0
        elif stack_ratio < 0.4:
            call_threshold = 0.55
            bet_threshold = 0.62
            bluff_freq = 0.0
        else:
            call_threshold = max(0.45, 0.58 - opponent_penalty)
            bet_threshold = max(0.50, 0.63 - opponent_penalty)
            bluff_freq = 0.15 if scary else 0.03

        street_num = {"flop": 1, "turn": 2, "river": 3}.get(street, 1)
        # Raise the call threshold each street you've already called
        call_threshold += (street_num - 1) * 0.06

        # pot odds for calling
        pot_odds = amount_owed / (pot + amount_owed) if amount_owed > 0 else 0

        # EV adjusted for aggressor tendency
        rf = get_raise_frequency(aggressor_seat) if aggressor_seat is not None else 0.2
        rf_adjustment = (rf - 0.2) * 50
        ev_call = equity * pot - (1 - equity) * amount_owed
        ev_call_adjusted = ev_call + rf_adjustment

        # kelly bet sizing
        kelly_fraction = max(0, 2 * equity - 1)
        street_multiplier = {"flop": 0.7, "turn": 0.85, "river": 1.0}.get(street, 1.0)
        bet_amount = int(kelly_fraction * pot * street_multiplier)
        bet_amount = max(bet_amount, min_raise_to)
        bet_amount = min(bet_amount, int(my_stack * 0.4))  # never bet more than 40% stack

        # continuation bet on flop if we raised preflop
        i_raised_preflop = hand_state.get(game_state["hand_id"], {}).get("raised_preflop", False)
        
        if street == "flop" and i_raised_preflop and amount_owed == 0 and equity > bet_threshold:
            cbet = max(min_raise_to, int(pot * 0.5))
            cbet = min(cbet, int(my_stack * 0.4))
            return {"action": "raise", "amount": cbet}

        if amount_owed == 0:
            if total_invested_this_hand > hand_investment_cap and equity < 0.70:
                return {"action": "check"}
            
            # bet for value
            if equity > bet_threshold:
                return {"action": "raise", "amount": bet_amount}

            # occasional bluff in late position
            if position > 0.6 and random.random() < bluff_freq and stack_ratio > 0.4:
                bluff = max(min_raise_to, int(pot * 0.5))
                bluff = min(bluff, int(my_stack * 0.25))
                return {"action": "raise", "amount": bluff}
            return {"action": "check"}

        else:
            # pot commitment check — if heavily invested, don't fold
            pot_committed = my_bet_this_street > my_stack * 0.4

            # facing a bet
            raises_this_street = sum(
                1 for e in action_log 
                if e.get("action") in ("raise", "all_in")
                and e.get("seat") != my_seat
            )

            # if already raised twice, just call instead of re-raising
            if raises_this_street >= 2 and equity < 0.85:
                if ev_call_adjusted > 0 and equity >call_threshold:
                    return {"action": "call"}
                if pot_committed and equity > pot_odds:
                    return {"action": "call"}
                return {"action": "fold"}

            if ev_call_adjusted > 0 and equity > call_threshold:
                # re-raise if very strong and not risking too much stack
                if equity > bet_threshold + 0.10 and amount_owed < my_stack * 0.35:
                    return {"action": "raise", "amount": bet_amount}
                return {"action": "call"}
            if can_check:
                return {"action": "check"}
            if pot_committed and equity > pot_odds:
                return {"action": "call"}

    return {"action": "fold"}