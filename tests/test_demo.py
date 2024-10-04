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
        "| name       | version    | ready | deployed             |\n"
        "|------------|------------|-------|----------------------|\n"
        "| demo-ea-01 | 2024.10.1  | true  | 2024-10-22T11:23:10Z |\n"
        "| demo-ea-02 | 2024.10.1b | true  | 2024-10-28T14:53:55Z |\n"
        "| demo-ea-03 | 2024.10.1  | false | 2024-10-22T12:51:50Z |\n"
    )

    res = mock_run.run_cli("ps")

    assert expect in res
