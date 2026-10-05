import pandas as pd
import pytest

from optimization.utils.temporal_split import temporal_train_test_split, walk_forward_validation


def test_temporal_train_test_split_returns_three_chronological_splits():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="1h"),
            "feature_1": range(100),
            "target_win": [0, 1] * 50,
        }
    )

    train_df, val_df, test_df = temporal_train_test_split(
        df,
        target_col="target_win",
        test_size=0.2,
        validation_size=0.1,
        timestamp_col="timestamp",
    )

    assert len(train_df) == 70
    assert len(val_df) == 10
    assert len(test_df) == 20

    assert train_df["timestamp"].max() < val_df["timestamp"].min()
    assert val_df["timestamp"].max() < test_df["timestamp"].min()


def test_temporal_train_test_split_sorts_input_by_timestamp():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=50, freq="1h"),
            "feature": range(50),
            "target_win": [0, 1] * 25,
        }
    )
    df = df.sample(frac=1.0, random_state=1).reset_index(drop=True)

    train_df, val_df, test_df = temporal_train_test_split(df)

    assert train_df["timestamp"].is_monotonic_increasing
    assert val_df["timestamp"].is_monotonic_increasing
    assert test_df["timestamp"].is_monotonic_increasing


def test_walk_forward_validation_returns_expected_number_of_folds_and_monotonic_ranges():
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="1h"),
            "feature": range(100),
            "target_win": [0, 1] * 50,
        }
    )

    folds = walk_forward_validation(df, n_splits=3, train_size=0.7, timestamp_col="timestamp")
    assert len(folds) == 3

    prev_train_len = 0
    for train_df, test_df in folds:
        assert len(train_df) >= prev_train_len
        prev_train_len = len(train_df)
        assert train_df["timestamp"].max() <= test_df["timestamp"].min()


@pytest.mark.parametrize("test_size,validation_size", [(0.2, 0.1), (0.3, 0.0)])
def test_temporal_split_sizes_sum_to_total(test_size, validation_size):
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=101, freq="1h"),
            "feature": range(101),
            "target_win": [0, 1] * 50 + [0],
        }
    )

    train_df, val_df, test_df = temporal_train_test_split(
        df,
        test_size=test_size,
        validation_size=validation_size,
    )

    assert len(train_df) + len(val_df) + len(test_df) == len(df)
