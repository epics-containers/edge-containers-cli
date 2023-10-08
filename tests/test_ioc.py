def test_instances(mock_run):
    mock_run.set_response(
        "bl45p", "bl45p-ea-ioc-01", "https://github.com/epics-caontainers/bl45p"
    )
    mock_run.run_cli("ioc", "instances", "bl45p-ea-ioc-01")
