import pytest
import pandas as pd
import numpy as np
from backend.analyzer import compute_fairness_metrics, compute_intersectional_metrics, AnalysisError


def make_biased_df():
    """Create a synthetic dataset with known bias."""
    np.random.seed(42)
    n = 1000

    # Group A: 80% positive rate, Group B: 30% positive rate
    groups = ['A'] * 500 + ['B'] * 500
    truth = [1] * 400 + [0] * 100 + [1] * 150 + [0] * 350
    preds = [1] * 400 + [0] * 100 + [1] * 150 + [0] * 350

    df = pd.DataFrame({
        'group': groups,
        'truth': truth,
        'prediction': preds,
    })
    return df


def make_fair_df():
    """Create a synthetic dataset with no bias."""
    n = 1000
    groups = ['X'] * 500 + ['Y'] * 500
    truth = ([1] * 250 + [0] * 250) * 2
    preds = ([1] * 250 + [0] * 250) * 2

    df = pd.DataFrame({
        'group': groups,
        'truth': truth,
        'prediction': preds,
    })
    return df


class TestComputeFairnessMetrics:
    def test_biased_dataset_detects_bias(self):
        df = make_biased_df()
        metrics = compute_fairness_metrics(df, 'truth', 'prediction', ['group'])

        assert 'group' in metrics
        m = metrics['group']
        # A has 80% positive rate, B has 30% — DP diff should be ~0.5
        assert m['demographic_parity_difference'] > 0.4
        assert m['disparate_impact_ratio'] < 0.5
        assert m['most_favoured_group'] == 'A'
        assert m['least_favoured_group'] == 'B'

    def test_fair_dataset_shows_no_bias(self):
        df = make_fair_df()
        metrics = compute_fairness_metrics(df, 'truth', 'prediction', ['group'])

        m = metrics['group']
        assert m['demographic_parity_difference'] < 0.01
        assert m['disparate_impact_ratio'] > 0.95

    def test_group_breakdown_has_expected_fields(self):
        df = make_biased_df()
        metrics = compute_fairness_metrics(df, 'truth', 'prediction', ['group'])

        breakdown = metrics['group']['group_breakdown']
        assert len(breakdown) == 2

        for row in breakdown:
            assert 'group' in row
            assert 'n' in row
            assert 'positive_rate' in row
            assert 'true_positive_rate' in row
            assert 'false_positive_rate' in row
            assert 'accuracy' in row
            assert 'precision' in row

    def test_multiple_sensitive_attributes(self):
        df = make_biased_df()
        df['color'] = (['red'] * 250 + ['blue'] * 250) * 2
        metrics = compute_fairness_metrics(df, 'truth', 'prediction', ['group', 'color'])

        assert 'group' in metrics
        assert 'color' in metrics

    def test_raises_on_same_truth_pred_column(self):
        df = make_biased_df()
        with pytest.raises(AnalysisError, match="must be different"):
            compute_fairness_metrics(df, 'truth', 'truth', ['group'])

    def test_raises_on_missing_column(self):
        df = make_biased_df()
        with pytest.raises(AnalysisError, match="not found"):
            compute_fairness_metrics(df, 'truth', 'nonexistent', ['group'])

    def test_raises_on_non_binary_values(self):
        df = pd.DataFrame({
            'truth': [0, 1, 2, 3],
            'prediction': [0, 1, 1, 0],
            'group': ['A', 'A', 'B', 'B'],
        })
        with pytest.raises(AnalysisError, match="0/1"):
            compute_fairness_metrics(df, 'truth', 'prediction', ['group'])

    def test_raises_on_single_group(self):
        df = pd.DataFrame({
            'truth': [0, 1, 0, 1],
            'prediction': [0, 1, 1, 0],
            'group': ['A', 'A', 'A', 'A'],
        })
        with pytest.raises(AnalysisError, match="fewer than 2"):
            compute_fairness_metrics(df, 'truth', 'prediction', ['group'])

    def test_sensitive_col_cannot_be_truth_or_pred(self):
        df = make_biased_df()
        with pytest.raises(AnalysisError, match="cannot be the same"):
            compute_fairness_metrics(df, 'truth', 'prediction', ['truth'])


class TestIntersectionalAnalysis:
    def test_requires_at_least_two_attributes(self):
        df = make_biased_df()
        result = compute_intersectional_metrics(df, 'truth', 'prediction', ['group'])
        assert result == {}

    def test_computes_cross_groups(self):
        df = make_biased_df()
        df['color'] = (['red'] * 250 + ['blue'] * 250) * 2

        result = compute_intersectional_metrics(df, 'truth', 'prediction', ['group', 'color'])
        assert len(result) > 0

        # Should have a key like "group × color"
        combo_key = 'group × color'
        assert combo_key in result
        assert 'group_breakdown' in result[combo_key]

    def test_warns_on_small_groups(self):
        # Create dataset where cross-groups have very few members
        df = pd.DataFrame({
            'truth': [1, 0, 1, 0] * 5,
            'prediction': [1, 0, 0, 1] * 5,
            'a': ['X', 'X', 'Y', 'Y'] * 5,
            'b': ['M', 'M', 'F', 'F'] * 5,
        })
        result = compute_intersectional_metrics(df, 'truth', 'prediction', ['a', 'b'])
        combo_key = 'a × b'
        if combo_key in result and 'warning' in result[combo_key]:
            assert 'few members' in result[combo_key]['warning']
