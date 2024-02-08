from ec_cli.utils import csv_to_table, json_to_table, make_table_str


def test_make_table():
    data = {
        "Name": ["fred", "george", "amy"],
        "Hobby": ["photography", "eating lots of cake", "chasing birds"],
        "Age": ["72", "9", "2"],
    }
    table = make_table_str(data)
    expected = ""
    expected += "NAME   HOBBY               AGE\n"
    expected += "fred   photography         72 \n"
    expected += "george eating lots of cake 9  \n"
    expected += "amy    chasing birds       2  "

    assert table == expected


# this is about the most useful format we can get from helm list
# hence the json_to_table function
json_data = """
[
    {
        "name": "bl47p-ea-dcam-01",
        "namespace": "p47-iocs",
        "revision": "2",
        "updated": "2024-02-06 18:58:32.59037165 +0000 UTC",
        "status": "deployed",
        "chart": "ioc-instance-2.0.0+b2",
        "app_version": "0.0.1b1"
    },
    {
        "name": "bl47p-ea-dcam-02",
        "namespace": "p47-iocs",
        "revision": "1",
        "updated": "2024-02-06 18:59:50.179763264 +0000 UTC",
        "status": "deployed",
        "chart": "ioc-instance-2.0.0+b2",
        "app_version": "0.0.1b1"
    },
    {
        "name": "bl47p-ea-panda-01",
        "namespace": "p47-iocs",
        "revision": "1",
        "updated": "2024-02-06 19:00:12.93790685 +0000 UTC",
        "status": "deployed",
        "chart": "ioc-instance-2.0.0+b2",
        "app_version": "0.0.1b1"
    }
]"""


def test_json_to_table():
    table = json_to_table(json_data)

    table.pop("updated")
    table.pop("status")
    table.pop("chart")
    table_txt = make_table_str(table)

    expected = ""
    expected += "NAME              NAMESPACE REVISION APP_VERSION\n"
    expected += "bl47p-ea-dcam-01  p47-iocs  2        0.0.1b1    \n"
    expected += "bl47p-ea-dcam-02  p47-iocs  1        0.0.1b1    \n"
    expected += "bl47p-ea-panda-01 p47-iocs  1        0.0.1b1    "

    assert table_txt == expected


# this is about the most useful format we can get from kubectl get pods
# hence the csv_to_table function
csv_data = """name,namespace,revision,updated,status,chart,app_version
bl47p-ea-dcam-01,p47-iocs,2,2024-02-06 18:58:32.59037165 +0000 UTC,deployed,ioc-instance-2.0.0+b2,0.0.1b1
bl47p-ea-dcam-02,p47-iocs,1,2024-02-06 18:59:50.179763264 +0000 UTC,deployed,ioc-instance-2.0.0+b2,0.0.1b1
"""


def test_csv_to_table():
    table = csv_to_table(csv_data)

    table.pop("updated")
    table.pop("status")
    table.pop("chart")
    table_txt = make_table_str(table)

    expected = ""
    expected += "NAME             NAMESPACE REVISION APP_VERSION\n"
    expected += "bl47p-ea-dcam-01 p47-iocs  2        0.0.1b1    \n"
    expected += "bl47p-ea-dcam-02 p47-iocs  1        0.0.1b1    "

    assert table_txt == expected
