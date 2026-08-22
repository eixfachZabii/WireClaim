import argparse
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# .env zuverlässig über find_dotenv oder relativ zur Datei laden (mit override=True)
ENV_PATH = find_dotenv(usecwd=True) or (Path(__file__).resolve().parent / ".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

from src.api import get_decryption_key, list_games, submit_price


def main() -> None:
    parser = argparse.ArgumentParser(description="WireClaim Submission Runner")
    parser.add_argument("--game-id", type=int, default=0, help="Game ID (Default: 0)")
    parser.add_argument("--charge", type=float, default=410.0, help="Charge price a (Default: 410.0)")
    parser.add_argument("--limit", type=float, default=430.0, help="Acceptance limit b (Default: 430.0)")
    args = parser.parse_args()

    # 1. Verfügbare Spiele anzeigen
    games = list_games()
    print("Verfügbare Games:", games)

    # 2. Decryption Key für das Spiel abrufen
    key = get_decryption_key(args.game_id)
    print(f"Decryption Key für Game {args.game_id}: {key}")

    # 3. Preis submitten
    result = submit_price(
        game_id=args.game_id,
        charge_price=args.charge,
        acceptance_limit=args.limit,
    )

    # 4. Bestätigung ausgeben
    print("Submission Ergebnis:", result)


if __name__ == "__main__":
    main()
