# crimsonbot-fullhouse-poker-bot

# CrimsonBot

A No-Limit Texas Hold'em poker bot built for the [Fullhouse Hackathon 2026](https://fullhousehackathon.com), sponsored by Jane Street, SIG, Jump Trading, QRT, Da Vinci, Quadrature, Five Rings and Teza.

**Result:** Top 64 out of 500+ participants (finalist)

---

## Overview

CrimsonBot is a rule-based poker bot that combines precomputed equity tables, real-time Monte Carlo simulation, and opponent modelling to make decisions in 6-max No-Limit Texas Hold'em.

---

## How It Works

### Preflop
- Uses a precomputed equity lookup table (`preflop_equity.json`) mapping every starting hand to its win rate against a random range in a 6-max game
- Position-based thresholds — tighter in early position, looser on the button
- Explicit fold logic for 3-bet and 4-bet situations based on hand strength rather than pot odds, preventing the bot from calling off its stack with weak hands into raising wars
- Tracks whether it has already raised preflop to avoid re-raising into 4-bet territory with non-premium hands

### Postflop
- Real-time Monte Carlo simulation (`eval7` library) — runs 300–500 random board completions to estimate win probability against active opponents
- Kelly-criterion-inspired bet sizing — bets proportionally to edge, scaled by street
- Opponent modelling — tracks each opponent's raise frequency using a Bayesian estimator to detect aggressive players
- Survival mode — tightens thresholds significantly when stack drops below 20–40% of starting stack
- Investment guards — limits total chips committed per hand based on starting stack, preventing runaway losses on any single hand
- Raising war detection — monitors total raises in a hand and folds when too many raises have occurred relative to hand strength

### Key Bug Fixed (Qualifier 1 → Qualifier 2)
The original bot used pot odds to evaluate whether to call re-raises preflop. This was fundamentally flawed — as the pot grows from repeated raises, pot odds actually *decrease*, making every successive call look mathematically justified even with weak hands. The bot would call 5 re-raises in a row with hands like J4o because the pot odds kept appearing attractive.

The fix: explicit equity thresholds for 3-bet (equity > 0.68) and 4-bet+ (equity > 0.75) situations, bypassing pot odds entirely in re-raise scenarios. This took the bot from 97th place in qualifier 1 to top 10 in qualifier 2.

---

## Stack

- **Language:** Python
- **Hand evaluation:** `eval7`
- **Equity estimation:** Monte Carlo simulation
- **Data:** Precomputed preflop equity table (6-max, heads-up adjusted)

---

## Results

| Stage | Result |
|---|---|
| Qualifier 1 | 97th place, +2.7k avg delta |
| Qualifier 2 | Top 10, +3,883 BB/100 |
| Finals | Top 64 finalist |

---

## Limitations & Future Work

The main limitation is that Monte Carlo equity estimation runs against **random** opponent hands. In reality, an opponent who raises preflop, cbets the flop, bets the turn and river has a much stronger range than random. This causes systematic equity overestimation against aggressive opponents.

The natural next step would be **range-based equity estimation** — modelling opponent hand ranges based on their betting patterns and updating those ranges as the hand progresses, then computing equity against the realistic range rather than random cards.

---

## Project Structure

```
├── bot.py                  # Main bot logic
└── data/
    └── preflop_equity.json # Precomputed 6-max equity table
```
