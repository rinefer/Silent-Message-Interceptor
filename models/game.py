import random
import asyncio

from telethon import events

from config import blackjack_games, poker_games, tictactoe_games, rps_stats


# Render a 3x3 tic-tac-toe board as a Unicode string
def draw_board(board):
    return (
        f"{board[0]}│{board[1]}│{board[2]}\n"
        f"──┼──┼──\n"
        f"{board[3]}│{board[4]}│{board[5]}\n"
        f"──┼──┼──\n"
        f"{board[6]}│{board[7]}│{board[8]}"
    )


# Return the winning symbol or None if no winner yet
def check_winner(board):
    WIN_LINES = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6],
    ]
    for line in WIN_LINES:
        a, b, c = line
        if board[a] == board[b] == board[c] != '⬛️':
            return board[a]
    return None


# Pick the best bot move: win > block > centre > corner > random
def bot_move(board):
    for symbol in ('⭕', '❌'):
        for i in range(9):
            if board[i] == '⬛️':
                copy = board.copy()
                copy[i] = symbol
                if check_winner(copy) == symbol:
                    return i

    if board[4] == '⬛️':
        return 4

    corners = [0, 2, 6, 8]
    random.shuffle(corners)
    for c in corners:
        if board[c] == '⬛️':
            return c

    free = [i for i, cell in enumerate(board) if cell == '⬛️']
    return random.choice(free) if free else None


# Format a poker hand as a numbered list
def format_hand(hand):
    return "\n".join(f"{i + 1}. {card}" for i, card in enumerate(hand))


# Evaluate a poker hand and return (combination_name, strength 1-10)
def evaluate_poker_hand(hand):
    RANK_MAP = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
        '7': 7, '8': 8, '9': 9, '10': 10,
        'J': 11, 'Q': 12, 'K': 13, 'A': 14,
    }
    ranks, suits = [], []
    for card in hand:
        rank = card[:2] if len(card) == 3 else card[0]
        suit = card[2]  if len(card) == 3 else card[1]
        ranks.append(RANK_MAP[rank])
        suits.append(suit)

    ranks       = sorted(ranks)
    rank_counts = {r: ranks.count(r) for r in set(ranks)}
    values      = sorted(rank_counts.values(), reverse=True)
    is_flush    = len(set(suits)) == 1
    is_straight = len(set(ranks)) == 5 and (ranks[-1] - ranks[0] == 4)

    if is_flush and ranks == [10, 11, 12, 13, 14]: return ("Royal Flush",    10)
    if is_flush and is_straight:                    return ("Straight Flush",  9)
    if 4 in values:                                 return ("Four of a Kind",  8)
    if sorted(values) == [2, 3]:                    return ("Full House",      7)
    if is_flush:                                    return ("Flush",           6)
    if is_straight:                                 return ("Straight",        5)
    if 3 in values:                                 return ("Three of a Kind", 4)
    if values.count(2) == 2:                        return ("Two Pair",        3)
    if 2 in values:                                 return ("One Pair",        2)
    return                                                  ("High Card",      1)


# Determine rock-paper-scissors result (1=rock, 2=scissors, 3=paper)
def determine_rps_winner(user, bot):
    if user == bot:
        return "🤝 Draw!"
    wins = {(1, 2), (2, 3), (3, 1)}
    return "🎉 You won!" if (user, bot) in wins else "😢 You lost!"


def register_game_handlers(client):

    # Spin the slot machine with a short animation
    @client.on(events.NewMessage(pattern='/slots'))
    async def slots_game(event):
        symbols = ["🍒", "🍋", "🍊", "🔔", "⭐", "7️⃣"]
        msg = await event.respond("🎰 Spinning the reels...")

        for _ in range(3):
            s = [random.choice(symbols) for _ in range(3)]
            await msg.edit(f"{' | '.join(s)}")
            await asyncio.sleep(0.3)

        final = [random.choice(symbols) for _ in range(3)]
        if final[0] == final[1] == final[2]:
            outcome = "🎉 JACKPOT!"
        elif final[0] == final[1] or final[1] == final[2]:
            outcome = "💰 Two of a kind!"
        else:
            outcome = "😢 Better luck next time!"

        await msg.edit(f"🎰 Result: {' | '.join(final)}\n\n{outcome}")

    # Start a new blackjack session for the caller
    @client.on(events.NewMessage(pattern='/blackjack'))
    async def start_blackjack(event):
        uid  = event.sender_id
        deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11] * 4
        random.shuffle(deck)

        blackjack_games[uid] = {
            'deck':        deck,
            'player_hand': [deck.pop(), deck.pop()],
            'dealer_hand': [deck.pop(), deck.pop()],
            'message':     None,
        }
        game = blackjack_games[uid]

        if sum(game['player_hand']) == 21:
            await event.respond(
                f"🃏 Your cards: {game['player_hand']} (21)\n"
                f"Dealer cards: {game['dealer_hand']}\n\n"
                "🎉 BLACKJACK! You win!"
            )
            del blackjack_games[uid]
            return

        game['message'] = await event.respond(
            f"🃏 Your cards: {game['player_hand']} (Sum: {sum(game['player_hand'])})\n"
            f"Dealer card: [{game['dealer_hand'][0]}, ?]\n\n"
            "Type **hit** to draw a card or **stand** to stop."
        )

    # Handle hit/stand moves for an active blackjack session
    @client.on(events.NewMessage)
    async def handle_blackjack(event):
        uid = event.sender_id
        if uid not in blackjack_games:
            return

        game = blackjack_games[uid]
        cmd  = event.text.lower().strip()

        if cmd == 'hit':
            game['player_hand'].append(game['deck'].pop())
            total = sum(game['player_hand'])
            if total > 21:
                await game['message'].edit(
                    f"💥 Bust! Your cards: {game['player_hand']} (Sum: {total})\n"
                    f"Dealer cards: {game['dealer_hand']}\n\n"
                    "You lost!\n\nType /blackjack to play again."
                )
                del blackjack_games[uid]
            else:
                await game['message'].edit(
                    f"🃏 Your cards: {game['player_hand']} (Sum: {total})\n"
                    f"Dealer card: [{game['dealer_hand'][0]}, ?]\n\n"
                    "Type **hit** or **stand**."
                )

        elif cmd == 'stand':
            while sum(game['dealer_hand']) < 17:
                game['dealer_hand'].append(game['deck'].pop())

            ps = sum(game['player_hand'])
            ds = sum(game['dealer_hand'])
            if ds > 21 or ps > ds:
                result = "🎉 You win!"
            elif ps == ds:
                result = "🤝 Draw!"
            else:
                result = "💥 Dealer wins!"

            await game['message'].edit(
                f"🃏 Your cards: {game['player_hand']} (Sum: {ps})\n"
                f"Dealer cards: {game['dealer_hand']} (Sum: {ds})\n\n"
                f"{result}\n\nType /blackjack to play again."
            )
            del blackjack_games[uid]

    # Deal 5 cards and start an American poker session (up to 5 exchanges)
    @client.on(events.NewMessage(pattern='/poker'))
    async def start_poker(event):
        uid   = event.sender_id
        suits = ['♥', '♦', '♣', '♠']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck  = [f"{r}{s}" for s in suits for r in ranks]
        random.shuffle(deck)

        hand = [deck.pop() for _ in range(5)]
        poker_games[uid] = {
            'deck':           deck,
            'player_hand':    hand,
            'message':        None,
            'exchange_count': 0,
            'max_exchanges':  5,
        }

        poker_games[uid]['message'] = await event.respond(
            f"🎴 **American Poker** (exchanges left: 5)\n\n"
            f"Your cards:\n{format_hand(hand)}\n\n"
            "Send card numbers to exchange (e.g.: 1 3 5)\n"
            "Or type **stop** to finish  |  **evaluate** to check your hand."
        )

    # Handle card exchanges, stop and evaluate in an active poker session
    @client.on(events.NewMessage)
    async def handle_poker(event):
        uid = event.sender_id
        if uid not in poker_games:
            return

        game = poker_games[uid]
        txt  = event.text.lower().strip()

        if txt == 'stop':
            combo, strength = evaluate_poker_hand(game['player_hand'])
            await game['message'].edit(
                f"🎴 **Final hand** (exchanges: {game['exchange_count']}/{game['max_exchanges']})\n\n"
                f"{format_hand(game['player_hand'])}\n\n"
                f"📊 **Combination:** {combo}\n"
                f"💪 **Strength:** {strength}/10\n\n"
                "Type /poker to play again."
            )
            del poker_games[uid]

        elif txt == 'evaluate':
            combo, strength = evaluate_poker_hand(game['player_hand'])
            await event.respond(
                f"📊 **Current evaluation:**\n"
                f"Combination: {combo}\n"
                f"Strength: {strength}/10\n"
                f"Exchanges left: {game['max_exchanges'] - game['exchange_count']}"
            )

        elif txt.replace(' ', '').isdigit():
            if game['exchange_count'] >= game['max_exchanges']:
                await event.respond("❌ Exchange limit reached! Type **stop**.")
                return
            try:
                indices = sorted(
                    [int(i) - 1 for i in txt.split() if i.isdigit()],
                    reverse=True
                )
                if not all(0 <= idx < 5 for idx in indices):
                    await event.respond("❌ Card numbers must be between 1 and 5.")
                    return
                for idx in indices:
                    if game['deck']:
                        game['player_hand'][idx] = game['deck'].pop()
                game['exchange_count'] += 1
                left = game['max_exchanges'] - game['exchange_count']
                await game['message'].edit(
                    f"🎴 **Poker** (exchanges left: {left})\n\n"
                    f"Your cards:\n{format_hand(game['player_hand'])}\n\n"
                    "Send card numbers to exchange (e.g.: 1 3 5)\n"
                    "Or type **stop** / **evaluate**."
                )
            except Exception as exc:
                await event.respond(f"❌ Error: {exc}")

        else:
            await event.respond(
                "❌ Unknown input. Use:\n"
                "• Card numbers to exchange (e.g.: 1 3 5)\n"
                "• **stop** — end the round\n"
                "• **evaluate** — check your hand"
            )

    # Start a tic-tac-toe game vs bot or another user
    @client.on(events.NewMessage(pattern='/ttt'))
    async def start_tictactoe(event):
        args = event.text.split()

        if len(args) == 1:
            player = event.sender_id
            tictactoe_games[player] = {
                'board':          ['⬛️'] * 9,
                'players':        {player: '❌', 'bot': '⭕'},
                'current_player': player,
                'message_id':     None,
                'vs_bot':         True,
            }
            msg = await event.respond(
                f"🎮 Tic-Tac-Toe (vs bot)\n\n"
                f"You: ❌  |  Bot: ⭕\n\n"
                f"{draw_board(tictactoe_games[player]['board'])}\n\n"
                "Your move! Choose a cell (1–9):\n"
                "1️⃣ 2️⃣ 3️⃣\n4️⃣ 5️⃣ 6️⃣\n7️⃣ 8️⃣ 9️⃣"
            )
            tictactoe_games[player]['message_id'] = msg.id
            return

        try:
            opponent = await client.get_entity(args[1])
        except Exception:
            await event.respond("❌ User not found.")
            return

        p1, p2 = event.sender_id, opponent.id
        if p1 == p2:
            await event.respond("🤨 You can't play against yourself!")
            return

        tictactoe_games[(p1, p2)] = {
            'board':          ['⬛️'] * 9,
            'players':        {p1: '❌', p2: '⭕'},
            'current_player': p1,
            'message_id':     None,
            'vs_bot':         False,
        }
        msg = await event.respond(
            f"🎮 Tic-Tac-Toe\n\n"
            f"Player 1: ❌ (you)\n"
            f"Player 2: ⭕ (@{opponent.username})\n\n"
            f"{draw_board(tictactoe_games[(p1, p2)]['board'])}\n\n"
            f"Current move: ❌\n"
            "Choose a cell (1–9):\n"
            "1️⃣ 2️⃣ 3️⃣\n4️⃣ 5️⃣ 6️⃣\n7️⃣ 8️⃣ 9️⃣"
        )
        tictactoe_games[(p1, p2)]['message_id'] = msg.id

    # Execute the bot's move with a 1-second thinking delay
    async def _make_bot_move(chat_id, game_key, game):
        await asyncio.sleep(1)
        move = bot_move(game['board'])
        if move is None:
            return

        game['board'][move] = '⭕'
        game['current_player'] = next(p for p in game['players'] if p != 'bot')

        winner = check_winner(game['board'])
        if winner:
            await client.edit_message(
                chat_id, game['message_id'],
                f"😢 Bot wins!\n\n{draw_board(game['board'])}\n\nType /ttt for a new game."
            )
            del tictactoe_games[game_key]
            return

        if '⬛️' not in game['board']:
            await client.edit_message(
                chat_id, game['message_id'],
                f"🤝 Draw!\n\n{draw_board(game['board'])}\n\nType /ttt for a new game."
            )
            del tictactoe_games[game_key]
            return

        await client.edit_message(
            chat_id, game['message_id'],
            f"🎮 Tic-Tac-Toe (vs bot)\n\n"
            f"You: ❌  |  Bot: ⭕\n\n"
            f"{draw_board(game['board'])}\n\n"
            "Your move! Choose a cell (1–9):\n"
            "1️⃣ 2️⃣ 3️⃣\n4️⃣ 5️⃣ 6️⃣\n7️⃣ 8️⃣ 9️⃣"
        )

    # Route a digit message to the correct tic-tac-toe game
    @client.on(events.NewMessage)
    async def handle_tictactoe_move(event):
        uid  = event.sender_id
        text = event.text.strip()

        game_key = None
        for key in tictactoe_games:
            if isinstance(key, tuple):
                if uid in key:
                    game_key = key
                    break
            elif key == uid:
                game_key = key
                break

        if game_key is None:
            return

        game = tictactoe_games[game_key]

        if uid != game['current_player']:
            tmp = await event.respond("⏳ It's not your turn!")
            await asyncio.sleep(2)
            await tmp.delete()
            await event.delete()
            return

        if not (text.isdigit() and len(text) == 1 and '1' <= text <= '9'):
            tmp = await event.respond("❌ Enter a number between 1 and 9.")
            await asyncio.sleep(2)
            await tmp.delete()
            await event.delete()
            return

        idx = int(text) - 1
        if game['board'][idx] != '⬛️':
            tmp = await event.respond("❌ That cell is already taken!")
            await asyncio.sleep(2)
            await tmp.delete()
            await event.delete()
            return

        game['board'][idx] = game['players'][uid]

        winner = check_winner(game['board'])
        if winner:
            if game['vs_bot']:
                result = "🎉 You win!" if winner == '❌' else "😢 Bot wins!"
            else:
                winner_id = next(p for p, s in game['players'].items() if s == winner)
                try:
                    we    = await client.get_entity(winner_id)
                    wname = f"@{we.username}" if getattr(we, 'username', None) else "Player"
                except Exception:
                    wname = "Player"
                result = f"🎉 Winner: {wname} ({winner})!"

            await event.client.edit_message(
                event.chat_id, game['message_id'],
                f"{result}\n\n{draw_board(game['board'])}\n\nType /ttt for a new game."
            )
            del tictactoe_games[game_key]
            await event.delete()
            return

        if '⬛️' not in game['board']:
            await event.client.edit_message(
                event.chat_id, game['message_id'],
                f"🤝 Draw!\n\n{draw_board(game['board'])}\n\nType /ttt for a new game."
            )
            del tictactoe_games[game_key]
            await event.delete()
            return

        if game['vs_bot']:
            game['current_player'] = 'bot'
            await event.delete()
            await _make_bot_move(event.chat_id, game_key, game)
        else:
            game['current_player'] = next(p for p in game['players'] if p != uid)
            try:
                np    = await client.get_entity(game['current_player'])
                nname = f"@{np.username}" if getattr(np, 'username', None) else "Player"
            except Exception:
                nname = "Player"

            p1e = await client.get_entity(game_key[0])
            p2e = await client.get_entity(game_key[1])
            await event.client.edit_message(
                event.chat_id, game['message_id'],
                f"🎮 Tic-Tac-Toe\n\n"
                f"Player 1: ❌ (@{p1e.username})\n"
                f"Player 2: ⭕ (@{p2e.username})\n\n"
                f"{draw_board(game['board'])}\n\n"
                f"Current move: {game['players'][game['current_player']]} ({nname})\n"
                "Choose a cell (1–9):\n"
                "1️⃣ 2️⃣ 3️⃣\n4️⃣ 5️⃣ 6️⃣\n7️⃣ 8️⃣ 9️⃣"
            )
            await event.delete()

    # Prompt the player to choose rock, scissors or paper
    @client.on(events.NewMessage(pattern='/rps'))
    async def rps_start(event):
        await event.respond(
            "🎮 **Rock-Paper-Scissors**\n\n"
            "Choose:\n"
            "1. ✊ Rock\n"
            "2. ✌️ Scissors\n"
            "3. ✋ Paper\n\n"
            "Just send the number."
        )

    # Resolve a rock-paper-scissors round
    @client.on(events.NewMessage)
    async def rps_play(event):
        if event.text.startswith('/'):
            return
        if not event.is_private:
            return
        if event.text.strip() not in ('1', '2', '3'):
            return

        uid         = event.sender_id
        user_choice = int(event.text.strip())
        bot_choice  = random.randint(1, 3)
        result      = determine_rps_winner(user_choice, bot_choice)

        NAMES = {1: ('✊', 'Rock'), 2: ('✌️', 'Scissors'), 3: ('✋', 'Paper')}

        if uid not in rps_stats:
            rps_stats[uid] = {'wins': 0, 'losses': 0, 'draws': 0}
        if 'won' in result.lower():
            rps_stats[uid]['wins']   += 1
        elif 'lost' in result.lower():
            rps_stats[uid]['losses'] += 1
        else:
            rps_stats[uid]['draws']  += 1

        stats = rps_stats[uid]
        ue, un = NAMES[user_choice]
        be, bn = NAMES[bot_choice]

        await event.respond(
            f"{ue} **{un}** vs {be} **{bn}**\n\n"
            f"**Result: {result}**\n\n"
            f"📊 *Stats:*\n"
            f"Wins: {stats['wins']} | Losses: {stats['losses']} | Draws: {stats['draws']}\n\n"
            "Play again? /rps"
        )
