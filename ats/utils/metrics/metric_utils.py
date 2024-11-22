import numpy as np


def find_sharp_ratio(returns_list, trading_days, daily_risk_free_rate=0.05/252) -> float:
    """
    Return the sharp ratio of a list of floats
    """

    risk_free_rate = daily_risk_free_rate * trading_days
    avg_return = np.mean(returns_list)
    std_return = np.std(returns_list)
    sharpe_ratio = (avg_return - risk_free_rate) / std_return

    return sharpe_ratio


def find_percentiles(data_list, time_list=False, time_scale_by_60=False):
    if time_list and time_scale_by_60:
        percentiles = {
            'min': np.round(np.min(data_list) / 60, 2),
            'p1': np.round(np.percentile(data_list, 1) / 60, 2),
            'p5': np.round(np.percentile(data_list, 5) / 60, 2),
            'p25': np.round(np.percentile(data_list, 25) / 60, 2),
            'p50': np.round(np.percentile(data_list, 50) / 60, 2),
            'p75': np.round(np.percentile(data_list, 75) / 60, 2),
            'p95': np.round(np.percentile(data_list, 95) / 60, 2),
            'p99': np.round(np.percentile(data_list, 99) / 60, 2),
            'max': np.round(np.max(data_list) / 60, 2),
        }

    else:
        percentiles = {
            'min': np.round(np.min(data_list), 2),
            'p1': np.round(np.percentile(data_list, 1), 2),
            'p5': np.round(np.percentile(data_list, 5), 2),
            'p25': np.round(np.percentile(data_list, 25), 2),
            'p50': np.round(np.percentile(data_list, 50), 2),
            'p75': np.round(np.percentile(data_list, 75), 2),
            'p95': np.round(np.percentile(data_list, 95), 2),
            'p99': np.round(np.percentile(data_list, 99), 2),
            'max': np.round(np.max(data_list), 2),
        }

    return percentiles


def metric_report(title_prefix=""):
    print("==" * 50)
    print("||" * 16, end="")
    print(
        f" {title_prefix}: Trade Report from Metric Evaluator " if title_prefix else " Trade Report from Metric Evaluator ",
        end="")
    print("||" * 16)
    print("==" * 50, end="\n")

