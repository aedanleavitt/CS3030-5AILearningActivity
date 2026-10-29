
import json
import socket
import threading

HOST = "127.0.0.1"
PORT = 5555

# Protect output when the receiver thread prints updates.
print_lock = threading.Lock()
game_finished = threading.Event()
my_symbol = None


def print_message(message):
    with print_lock:
        print(message, flush=True)


def display_board(board):
    """Print the board using 1-9 for empty squares."""
    cells = [
        str(i + 1) if value == " " else value
        for i, value in enumerate(board)
    ]

    print_message(
        f"\n {cells[0]} | {cells[1]} | {cells[2]} \n"
        "---+---+---\n"
        f" {cells[3]} | {cells[4]} | {cells[5]} \n"
        "---+---+---\n"
        f" {cells[6]} | {cells[7]} | {cells[8]} \n"
    )


def receive_messages(reader):
    """Continuously receive updates from the server."""
    try:
        for line in reader:
            message = json.loads(line)
            message_type = message.get("type")

            if message_type == "welcome":
                global my_symbol
                my_symbol = message["symbol"]
                print_message(f"\nYou are player {my_symbol}.")

            elif message_type == "state":
                print_message("\n--- Current board ---")
                display_board(message["board"])

                if message.get("status"):
                    print_message(message["status"])

                if message.get("game_over"):
                    game_finished.set()
                    break

                if message["current_player"] == my_symbol:
                    print_message("It is your turn.")
                else:
                    print_message(
                        f"Waiting for player {message['current_player']}..."
                    )

            elif message_type == "error":
                print_message(f"Invalid move: {message['message']}")

    except (OSError, ConnectionError, json.JSONDecodeError):
        pass

    finally:
        game_finished.set()
        print_message("Connection closed.")


def main():
    try:
        with socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        ) as client:
            print(f"Connecting to {HOST}:{PORT}...")

            client.connect((HOST, PORT))

            # A file wrapper lets us read newline-delimited messages.
            with client.makefile("r", encoding="utf-8") as reader:
                receiver = threading.Thread(
                    target=receive_messages,
                    args=(reader,),
                    daemon=True,
                )
                receiver.start()

                while not game_finished.is_set():
                    try:
                        choice = input(
                            "Enter a square (1-9), or q to quit: "
                        ).strip()

                    except (EOFError, KeyboardInterrupt):
                        break

                    if choice.lower() == "q":
                        break

                    if not choice.isdigit():
                        print("Enter a number from 1 to 9.")
                        continue

                    position = int(choice)

                    if not 1 <= position <= 9:
                        print("Enter a number from 1 to 9.")
                        continue

                    message = {
                        "type": "move",
                        "position": position,
                    }

                    try:
                        client.sendall(
                            (json.dumps(message) + "\n").encode("utf-8")
                        )
                    except OSError:
                        print("Could not send move. Connection lost.")
                        break

    except ConnectionRefusedError:
        print("Could not connect. Is server.py running?")
    except OSError as error:
        print(f"Connection error: {error}")

    print("Client exiting.")


if __name__ == "__main__":
    main()
