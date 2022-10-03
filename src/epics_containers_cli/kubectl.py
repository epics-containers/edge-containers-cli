# kubectl format strings
fmt_pods_wide = (
    "custom-columns="
    "IOC:metadata.name,"
    "VERSION:metadata.labels.ioc_version,"
    "STATE:status.containerStatuses[0].state.*.reason,"
    "RESTARTS:status.containerStatuses[0].restartCount,"
    "STARTED:metadata.managedFields[0].time,IP:status.podIP,"
    "IMAGE:spec.containers[0].image"
)
fmt_pods = (
    "custom-columns="
    "IOC:metadata.labels.app,"
    "VERSION:metadata.labels.ioc_version,"
    "STATE:status.containerStatuses[0].state.*.reason,"
    "RESTARTS:status.containerStatuses[0].restartCount,"
    "STARTED:metadata.managedFields[0].time"
)
fmt_deploys = (
    "custom-columns="
    "DEPLOYMENT:metadata.labels.app,"
    "VERSION:metadata.labels.ioc_version,"
    "REPLICAS:spec.replicas,"
    "IMAGE:spec.template.spec.containers[0].image"
)
fmt_services = (
    "custom-columns="
    "SERVICE:metadata.labels.app,"
    "CLUSTER-IP:spec.clusterIP,"
    "EXTERNAL-IP:status.loadBalancer.ingress[0].ip,"
    "PORT:spec.ports[*].targetPort"
)
