"""
WireClaim API Package.

Modules:
- `tournament`: QuantCo tournament API (list_games, get_decryption_key, submit_price, submit_prices)
- `llm`: Azure OpenAI / OpenAI LLM queries (get_llm_client, query_llm)
"""

from src.api.llm import get_llm_client, query_llm
from src.api.tournament import (
    get_decryption_key,
    list_games,
    print_submissions,
    submit_price,
    submit_prices,
)

__all__ = [
    # Tournament API
    "list_games",
    "get_decryption_key",
    "submit_price",
    "submit_prices",
    "print_submissions",
    # LLM API
    "get_llm_client",
    "query_llm",
]
