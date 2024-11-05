def test_logs(mock_run, DEMO):
    mock_run.run_cli("logs demo-ea-01")


def test_log_history(mock_run, DEMO):
    mock_run.run_cli("log-history demo-ea-01")


def test_restart(mock_run, DEMO):
    mock_run.run_cli("restart demo-ea-01")


def test_start(mock_run, DEMO):
    mock_run.run_cli("start demo-ea-01")


def test_stop(mock_run, DEMO):
    mock_run.run_cli("stop demo-ea-01")


def test_ps(mock_run, DEMO):
    expect = (
        "| name       | version | ready | deployed             |\n"
        "|------------|---------|-------|----------------------|\n"
        "| demo-ea-00 | 1.0.25  | true  | 2024-10-22T11:23:08Z |\n"
        "| demo-ea-01 | 1.0.24  | true  | 2024-10-22T11:23:03Z |\n"
        "| demo-ea-02 | 1.0.23  | true  | 2024-10-22T11:23:04Z |\n"
        "| demo-ea-03 | 1.0.22  | true  | 2024-10-22T11:23:07Z |\n"
        "| demo-ea-04 | 1.0.21  | true  | 2024-10-22T11:23:01Z |\n"
        "| demo-ea-05 | 1.0.20  | true  | 2024-10-22T11:23:03Z |\n"
        "| demo-ea-06 | 1.0.19  | true  | 2024-10-22T11:23:07Z |\n"
        "| demo-ea-07 | 1.0.18  | true  | 2024-10-22T11:23:01Z |\n"
    )

    res = mock_run.run_cli("ps")

    assert expect in res
