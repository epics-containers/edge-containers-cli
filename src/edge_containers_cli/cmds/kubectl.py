json_service_info = (
    "-o jsonpath='"
    r'{range .items[*]}{..labels.app}{","}{..containerStatuses[0].ready}'
    r'{","}{..containerStatuses[0].restartCount}{","}{.status.startTime}'
    r'{"\n"}{end}'
    "'"
)

# force all the values to be strings so there are never parsing errors
json_service_types = {"name": str, "ready": str, "restarts": str, "started": str}
