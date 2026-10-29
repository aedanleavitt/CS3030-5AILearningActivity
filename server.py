
import json
import socket
import threading
from queue import Queue

HOST = "127.0.0.1"
PORT = 5555

# Messages received from clients are placed in this queue.
messages = Queue()

# The two connected players and their symbols.
players = {}
send_locks = {}

board = [" "] * 9
current_player = "X"
game_over = False


def send_message(connection, message):
    """Send one JSON message, terminated by a newline."""
    data = json.dumps(message) + "\n"

    with send_locks[connection]:
        connection.sendall(data.encode("utf-8"))


def receive_messages(connection, symbol):
    """Read messages from one client in a separate thread."""
    try:
        with connection.makefile("r", encoding="utf-8") as reader:
            for line in reader:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue

                messages.put((symbol, message))

    except (OSError, ConnectionError):
        pass

    finally:
        messages.put((symbol, {"type": "disconnect"}))


def check_winner():
    """Return X or O if that player has won; otherwise return None."""
    winning_lines = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    ]

    for a, b, c in winning_lines:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]

    return None


def board_text():
    """Create a readable version of the board."""
    cells = [
        str(i + 1) if value == " " else value
        for i, value in enumerate(board)
    ]

    return (
        f" {cells[0]} | {cells[1]} | {cells[2]} \n"
        "---+---+---\n"
        f" {cells[3]} | {cells[4]} | {cells[5]} \n"
        "---+---+---\n"
        f" {cells[6]} | {cells[7]} | {cells[8]} "
    )


def broadcast_state(status=""):
    """Send the current game state to both players."""
    message = {
        "type": "state",
        "board": board,
        "current_player": current_player,
        "status": status,
        "game_over": game_over,
    }

    for connection in list(players):
        try:
            send_message(connection, message)
        except OSError:
            pass


def main():
    global current_player, game_over

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((HOST, PORT))
        server.listen(2)

        print(f"Server listening on {HOST}:{PORT}")
        print("Waiting for two players...")

        # Accept exactly two players.
        for symbol in ("X", "O"):
            connection, address = server.accept()
            players[connection] = symbol
            send_locks[connection] = threading.Lock()

            print(f"Player {symbol} connected from {address}")

            send_message(connection, {
                "type": "welcome",
                "symbol": symbol,
            })

        print("Both players connected. Game starting!")

        # Start a reader thread for each player.
        for connection, symbol in list(players.items()):
            thread = threading.Thread(
                target=receive_messages,
                args=(connection, symbol),
                daemon=True,
            )
            thread.start()

        broadcast_state("Game started! X goes first.")

        while not game_over:
            symbol, message = messages.get()

            # Stop the game if either player disconnects.
            if message.get("type") == "disconnect":
                game_over = True
                broadcast_state(
                    f"Player {symbol} disconnected. Game ended."
                )
                print(f"Player {symbol} disconnected.")
                break

            # Ignore messages that are not moves.
            if message.get("type") != "move":
                continue

            # Only the player whose turn it is may move.
            if symbol != current_player:
                send_message(
                    next(
                        conn for conn, player_symbol in players.items()
                        if player_symbol == symbol
                    ),
                    {
                        "type": "error",
                        "message": "It is not your turn.",
                    },
                )
                continue

            position = message.get("position")

            # Positions must be integers from 1 through 9.
            if type(position) is not int or not 1 <= position <= 9:
                connection = next(
                    conn for conn, player_symbol in players.items()
                    if player_symbol == symbol
                )
                send_message(connection, {
                    "type": "error",
                    "message": "Choose a position from 1 to 9.",
                })
                continue

            index = position - 1

            # A move cannot replace an existing mark.
            if board[index] != " ":
                connection = next(
                    conn for conn, player_symbol in players.items()
                    if player_symbol == symbol
                )
                send_message(connection, {
                    "type": "error",
                    "message": "That square is occupied.",
                })
                continue

            # Apply the valid move.
            board[index] = symbol

            winner = check_winner()

            if winner:
                game_over = True
                broadcast_state(f"Player {winner} wins!")
                print(f"\n{board_text()}\nPlayer {winner} wins!")
            elif " " not in board:
                game_over = True
                broadcast_state("The game is a draw!")
                print(f"\n{board_text()}\nThe game is a draw!")
            else:
                current_player = "O" if current_player == "X" else "X"
                broadcast_state(f"Player {symbol} played position {position}.")

        print("Game finished. Shutting down.")

    except (OSError, ConnectionError) as error:
        print(f"Server error: {error}")

    finally:
        for connection in list(players):
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()

        server.close()


if __name__ == "__main__":
    main()
