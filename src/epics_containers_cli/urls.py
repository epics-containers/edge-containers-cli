# given a beamline name and an ioc name, return the expected URL of the
# source repo containing IOC instance definitions
def get_repo_url(domain: str):
    # TODO replace github with environ variable
    return f"https://github.com/epics-containers/{domain}"
