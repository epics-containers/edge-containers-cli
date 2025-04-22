# The devcontainer should use the developer target and run as root with podman
# or docker with user namespaces.
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION} AS developer

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# install tools used by ec #####################################################

# ArgoCD CLI - see https://github.com/argoproj/argo-cd/releases
RUN VERSION=v2.14.10 && \
    curl -sSL -o argocd https://github.com/argoproj/argo-cd/releases/download/$VERSION/argocd-linux-amd64 && \
    echo "d1750274a336f0a090abf196a832cee14cb9f1c2fc3d20d80b0dbfeff83550fa argocd" | sha256sum -c && \
    install -m 555 argocd /usr/local/bin/argocd && \
     rm argocd

# kubectl - see https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/
RUN VERSION=v1.32.3 && \
    curl -sSLO https://dl.k8s.io/release/$VERSION/bin/linux/amd64/kubectl && \
    echo "ab209d0c5134b61486a0486585604a616a5bb2fc07df46d304b3c95817b2d79f kubectl" | sha256sum -c && \
    install -m 555 kubectl /usr/local/bin/kubectl && \
    rm kubectl

# helm - see https://github.com/helm/helm/releases
RUN VERSION=v3.17.3 && \
    curl -sSL -o helm.tar.gz https://get.helm.sh/helm-$VERSION-linux-amd64.tar.gz && \
    echo "ee88b3c851ae6466a3de507f7be73fe94d54cbf2987cbaa3d1a3832ea331f2cd helm.tar.gz" | sha256sum -c && \
    tar -xzf helm.tar.gz --strip-components=1 linux-amd64/helm && \
    install -m 555 helm /usr/local/bin/helm && \
    rm helm.tar.gz

# install the context into the venv
COPY . /context
WORKDIR /context
RUN touch dev-requirements.txt && \
    pip install -c dev-requirements.txt .

ENTRYPOINT ["ec"]
CMD ["--version"]
