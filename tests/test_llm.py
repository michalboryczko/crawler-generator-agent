"""Tests for LLM client module."""

import pytest

from src.core.llm import MODEL_COSTS, estimate_cost


class TestEstimateCost:
    """Tests for estimate_cost function."""

    def test_known_model(self):
        """Test cost estimation for known model."""
        cost = estimate_cost("gpt-4o", tokens_input=1000, tokens_output=500)
        expected = (1000 / 1000) * 0.0025 + (500 / 1000) * 0.01
        assert cost == pytest.approx(expected)

    def test_mini_model_cheaper(self):
        """Test mini model is cheaper than full model."""
        full_cost = estimate_cost("gpt-4o", tokens_input=1000, tokens_output=500)
        mini_cost = estimate_cost("gpt-4o-mini", tokens_input=1000, tokens_output=500)
        assert mini_cost < full_cost

    def test_unknown_model_zero_cost(self):
        """Test unknown model returns zero cost."""
        cost = estimate_cost("unknown-model", tokens_input=1000, tokens_output=500)
        assert cost == 0.0

    def test_zero_tokens(self):
        """Test zero tokens returns zero cost."""
        cost = estimate_cost("gpt-4o", tokens_input=0, tokens_output=0)
        assert cost == 0.0

    def test_large_token_count(self):
        """Test with large token counts."""
        cost = estimate_cost("gpt-4o", tokens_input=100000, tokens_output=50000)
        assert cost > 0
        # Verify calculation is correct
        expected = (100000 / 1000) * 0.0025 + (50000 / 1000) * 0.01
        assert cost == pytest.approx(expected)


class TestModelCosts:
    """Tests for MODEL_COSTS constant."""

    def test_model_costs_has_gpt4o(self):
        """Test MODEL_COSTS includes gpt-4o."""
        assert "gpt-4o" in MODEL_COSTS
        assert "input" in MODEL_COSTS["gpt-4o"]
        assert "output" in MODEL_COSTS["gpt-4o"]

    def test_model_costs_has_gpt4o_mini(self):
        """Test MODEL_COSTS includes gpt-4o-mini."""
        assert "gpt-4o-mini" in MODEL_COSTS

    def test_model_costs_all_have_input_output(self):
        """Test all model costs have input and output keys."""
        for model, costs in MODEL_COSTS.items():
            assert "input" in costs, f"{model} missing input cost"
            assert "output" in costs, f"{model} missing output cost"

    def test_model_costs_positive_values(self):
        """Test all costs are non-negative."""
        for model, costs in MODEL_COSTS.items():
            assert costs["input"] >= 0, f"{model} has negative input cost"
            assert costs["output"] >= 0, f"{model} has negative output cost"

    def test_output_typically_more_expensive(self):
        """Test output tokens are typically more expensive than input."""
        # This is true for most LLM pricing models
        models_with_output_more_expensive = 0
        for _model, costs in MODEL_COSTS.items():
            if costs["input"] > 0 and costs["output"] > costs["input"]:
                models_with_output_more_expensive += 1

        # Most models should have more expensive output
        assert models_with_output_more_expensive > len(MODEL_COSTS) // 2
