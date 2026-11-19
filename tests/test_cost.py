
import pytest

from app.services.cost import calculate_cost


def test_normal_cost():
    result = calculate_cost(
        api_calls=3,
        input_tokens=100,
        cached_input_tokens=0,
        output_tokens=50,
        reasoning_tokens=0
    )

    assert result["token_cost_micro_usd"] == 30
    assert result["api_cost_micro_usd"] == 300
    assert result["total_cost_micro_usd"] == 330
    assert result["total_cost_usd"] == 0.00033


def test_cached_token_cost():
    result = calculate_cost(
        api_calls=1,
        input_tokens=100,
        cached_input_tokens=40,
        output_tokens=50,
        reasoning_tokens=10
    )

    assert result["token_cost_micro_usd"] == 27
    assert result["api_cost_micro_usd"] == 100
    assert result["total_cost_micro_usd"] == 127
    assert result["total_cost_usd"] == 0.000127


def test_zero_usage_cost():
    result = calculate_cost(
        api_calls=0,
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0
    )

    assert result["total_cost_micro_usd"] == 0
    assert result["total_cost_usd"] == 0


def test_reasoning_tokens_are_not_double_counted():
    result = calculate_cost(
        api_calls=0,
        input_tokens=0,
        cached_input_tokens=0,
        output_tokens=50,
        reasoning_tokens=20
    )

    assert result["token_cost_micro_usd"] == 20
