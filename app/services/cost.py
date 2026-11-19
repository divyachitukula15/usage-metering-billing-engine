
from app.config import (
    INPUT_TOKEN_PRICE,
    CACHED_INPUT_TOKEN_PRICE,
    OUTPUT_TOKEN_PRICE,
    API_CALL_PRICE,
    MICRO_USD,
    TOKENS_PER_MILLION
)


def calculate_cost(
    api_calls: int,
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int
):
    billable_input = input_tokens - cached_input_tokens

    total_output = output_tokens 
    cost = (
        (billable_input * INPUT_TOKEN_PRICE)
        + (cached_input_tokens * CACHED_INPUT_TOKEN_PRICE)
        + (total_output * OUTPUT_TOKEN_PRICE)
    ) // TOKENS_PER_MILLION

    api_cost = api_calls * API_CALL_PRICE

    total_cost = cost + api_cost

    return {
        "token_cost_micro_usd": cost,
        "api_cost_micro_usd": api_cost,
        "total_cost_micro_usd": total_cost,
        "total_cost_usd": total_cost / MICRO_USD
    }
