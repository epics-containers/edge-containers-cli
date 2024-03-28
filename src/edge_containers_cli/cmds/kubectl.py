jsonpath_pod_info = (
    "-o jsonpath='"
    r'{range .items[*]}{..labels.app}{..labels.app\.kubernetes\.io/instance}{","}{.status.phase}'
    r'{","}{..containerStatuses[0].restartCount}'
    r'{"\n"}{end}'
    "'"
)

jsonpath_deploy_info = (
    "-o jsonpath='"
    r'{range .items[*]}{.metadata.name}{","}'
    r"{range .spec.template.spec.containers[*]}{.image}"
    r'{"\n"}{end}{end}'
    "'"
)
