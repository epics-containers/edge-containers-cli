# Environment variables

Every [global option](global-options) of `ec` has an equivalent
environment variable. Setting them once — in your shell profile, a `.env` file,
or a Kubernetes/CI environment — saves repeating `--repo`, `--target` and
`--backend` on every call.

A command-line option always overrides the matching environment variable, which
in turn overrides the built-in default.

:::{tip}
Run `ec env` at any time to print every variable below and its current value:

```
$ ec env
EC_SERVICES_REPO=https://github.com/my-org/my-beamline-services
EC_TARGET=Not Defined
EC_LOGIN=Not Defined
EC_CLI_BACKEND=K8S
EC_VERBOSE=Not Defined
EC_DRYRUN=Not Defined
EC_DEBUG=Not Defined
EC_LOG_LEVEL=Not Defined
EC_LOG_URL=Not Defined
```
:::

## Reference

| Variable | Option | Default | Description |
| :--- | :--- | :--- | :--- |
| `EC_SERVICES_REPO` | `-r`, `--repo` | *(unset)* | Git repository holding the service instance definitions. |
| `EC_TARGET` | `-t`, `--target` | *(unset)* | Deployment target: a Kubernetes namespace (`K8S`) or `app-namespace/root-app` (`ARGOCD`). |
| `EC_CLI_BACKEND` | `-b`, `--backend` | `ARGOCD` | Backend to drive: `ARGOCD`, `K8S` or `DEMO`. |
| `EC_VERBOSE` | `-v`, `--verbose` | `False` | Print each underlying command before running it. |
| `EC_DRYRUN` | `--dryrun` | `False` | Print the underlying commands without executing them. |
| `EC_DEBUG` | `-d`, `--debug` | `False` | Enable debug logging and keep temporary working directories. |
| `EC_LOG_LEVEL` | `--log-level` | `WARNING` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `EC_LOG_URL` | `--log-url` | *(unset)* | Endpoint used by `ec log-history` to open historical logs. |
| `EC_LOGIN` | *(none)* | *(unset)* | ArgoCD login command — see below. **No command-line equivalent.** |

## Notes on individual variables

### `EC_SERVICES_REPO`

The git repository that defines your services. Required by `list`, `instances`,
`deploy` and any command that resolves a service version. If unset, those
commands fail with *"Please set `EC_SERVICES_REPO` or pass --repo"*.

### `EC_TARGET`

Where services are deployed. The meaning depends on the backend:

- **K8S** — the Kubernetes namespace, e.g. `bl01t-iocs`.
- **ARGOCD** — the ArgoCD application in `app-namespace/root-app` form.

Required by any command that touches the cluster; unset, they fail with
*"Please set `EC_TARGET` or pass --target"*.

### `EC_CLI_BACKEND`

Chooses the backend (`ARGOCD`, `K8S`, `DEMO`). Because the backend determines
which commands exist, this also affects `ec --help`. See
[Backends](backends).

### `EC_LOGIN`

Used only by the `ARGOCD` backend. If `ec` finds the ArgoCD server is
unauthenticated while validating the target, and `EC_LOGIN` is set, it offers to
run its value as a login command and then retries — for example:

```
$ export EC_LOGIN="argocd login my-argocd.example.com --sso"
```

If `EC_LOGIN` is unset, `ec` instead fails with *"Not authenticated to argocd
server"*. This variable has **no** command-line flag because it may contain
credentials; keep it in your environment, not your shell history.

### `EC_VERBOSE`, `EC_DRYRUN`, `EC_DEBUG`

Diagnostic switches. `EC_VERBOSE` echoes each underlying command; `EC_DRYRUN`
echoes them *without* running anything (useful for learning the equivalent
`git`/`kubectl`/`helm`/`argocd` invocations); `EC_DEBUG` raises the log level to
`DEBUG` and retains the temporary working directories `ec` would otherwise clean
up.

Set any of these to a truthy value (e.g. `1`) to enable.
