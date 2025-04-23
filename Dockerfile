# This container is used for deploying ec as an apptainer container including
# the CLI tools it uses. See https://github.com/DiamondLightSource/deploy-tools
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION} AS developer

# Set up a virtual environment and put it in PATH
RUN python -m venv /venv
ENV PATH=/venv/bin:$PATH

# install the context into the venv
COPY . /context
WORKDIR /context
RUN touch dev-requirements.txt && \
    pip install -c dev-requirements.txt .

ENTRYPOINT ["ec"]
CMD ["--version"]
