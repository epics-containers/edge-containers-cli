# kubectl format strings
fmt_pods_wide = (
    "custom-columns="
    "POD:metadata.name,"
    "VERSION:metadata.labels.ioc_version,"
    "STATE:status.phase,"
    "RESTARTS:status.containerStatuses[0].restartCount,"
    "STARTED:metadata.managedFields[0].time,IP:status.podIP,"
    "GENERIC_IOC_IMAGE:spec.containers[0].image"
)
fmt_pods = (
    "custom-columns="
    "IOC_NAME:metadata.labels.app,"
    "VERSION:metadata.labels.ioc_version,"
    "STATE:status.phase,"
    "RESTARTS:status.containerStatuses[0].restartCount,"
    "STARTED:metadata.managedFields[0].time"
)
fmt_deploys = (
    "custom-columns="
    "DEPLOYMENT:metadata.labels.app,"
    "VERSION:metadata.labels.ioc_version,"
    "RUNNING:spec.replicas,"
    "GENERIC_IOC_IMAGE:spec.template.spec.containers[0].image"
)
fmt_services = (
    "custom-columns="
    "SERVICE:metadata.labels.app,"
    "CLUSTER-IP:spec.clusterIP,"
    "EXTERNAL-IP:status.loadBalancer.ingress[0].ip,"
    "PORT:spec.ports[*].targetPort"
)
json_service_info = (
    "-o jsonpath='"
    r'{range .items[*]}{..labels.app}{","}{..containerStatuses[0].ready}'
    r'{","}{..containerStatuses[0].restartCount}{","}{.status.startTime}'
    r'{"\n"}{end}'
    "'"
)
json_service_headers = ["name", "ready", "restarts", "started"]
