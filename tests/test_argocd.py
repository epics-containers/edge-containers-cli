def test_logs(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.logs)
    mock_run.run_cli("logs bl01t-ea-test-01")


def test_log_history(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.log_history)
    mock_run.run_cli("log-history bl01t-ea-test-01")


def test_restart(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.restart)
    mock_run.run_cli("restart bl01t-ea-test-01")


def test_start(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.start)
    mock_run.run_cli("start bl01t-ea-test-01")


def test_stop(mock_run, ARGOCD):
    mock_run.set_seq(ARGOCD.checks + ARGOCD.stop)
    mock_run.run_cli("stop bl01t-ea-test-01")


def test_ps(mock_run, ARGOCD):
    expect = (
        "| name             | version | ready | deployed             |\n"
        "|------------------|---------|-------|----------------------|\n"
        "| bl01t-ea-test-01 | main    | true  | 2024-07-12T13:52:35Z |\n"
    )
    mock_run.set_seq(ARGOCD.checks)
    res = mock_run.run_cli("ps")

    assert res == expect