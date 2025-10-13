#!/usr/bin/env python3
import numpy as np
import pandas as pd


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_pred - y_true)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_pred - y_true) ** 2)))


def smape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    denom = (np.abs(y_true) + np.abs(y_pred)).clip(min=eps)
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / denom))


def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-8) -> float:
    denom = np.abs(y_true).clip(min=eps)
    return float(np.mean(np.abs(y_pred - y_true) / denom))


def peak_timing_error(y_true: pd.Series, y_pred: pd.Series) -> float:
    """Return absolute difference in index positions of peak values.
    Assumes aligned indices in time order.
    """
    if len(y_true) == 0 or len(y_pred) == 0:
        return float("nan")
    i_true = int(np.argmax(y_true.values))
    i_pred = int(np.argmax(y_pred.values))
    return float(abs(i_pred - i_true))


def coverage(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    inside = (y_true >= lower) & (y_true <= upper)
    return float(np.mean(inside.astype(float)))
