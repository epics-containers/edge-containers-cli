# Command line reference

`ec` is a thin wrapper around the tools you would otherwise drive by hand
(`git`, `kubectl`, `helm`, `argocd`). Every invocation has the form:

```
$ ec [GLOBAL OPTIONS] COMMAND [ARGS] [COMMAND OPTIONS]
```

The set of commands and options that `ec` exposes is **not fixed** — it depends
on the [backend](backends) you select. Commands a backend cannot implement are
removed from the CLI entirely, and a handful of options are added or removed per
backend. This page describes the full command surface and notes where it varies.

:::{tip}
The CLI is self-documenting. `ec --help` lists the commands available for the
current backend, and `ec COMMAND --help` describes a single command. Because the
backend is chosen *before* help is rendered, `ec -b K8S --help` and
`ec -b DEMO --help` show different command lists.
:::

(global-options)=
## Global options

Global options come *before* the command. Each one can also be set through an
[environment variable](environment-variables.md), which is often more convenient
for values you reuse across every call (such as the repository and target).

| Option | Environment variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `--version` | — | — | Print the version of `ec` and exit. |
| `-r`, `--repo` | `EC_SERVICES_REPO` | *(unset)* | Git repository holding the service instance definitions. |
| `-t`, `--target` | `EC_TARGET` | *(unset)* | The deployment target: a Kubernetes namespace (K8S) or an `app-namespace/root-app` (ARGOCD). |
| `-b`, `--backend` | `EC_CLI_BACKEND` | `ARGOCD` | Backend to drive: `ARGOCD`, `K8S` or `DEMO`. |
| `-v`, `--verbose` | `EC_VERBOSE` | `False` | Print each underlying command before it is run. |
| `--dryrun` | `EC_DRYRUN` | `False` | Print the underlying commands but do **not** execute them. |
| `-d`, `--debug` | `EC_DEBUG` | `False` | Enable debug logging and retain temporary working directories. |
| `--log-level` | `EC_LOG_LEVEL` | `WARNING` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `--log-url` | `EC_LOG_URL` | *(unset)* | Endpoint used by `log-history` to open historical logs. |

:::{note}
`--repo`, `--target` and `--log-url` have no usable default. A command that
needs one will fail with a clear message (for example *"Please set `EC_TARGET`
or pass --target"*) until you provide it. See
[Environment variables](environment-variables.md) for the recommended way to set
them once.
:::

(backends)=
## Backends

A *backend* determines how `ec` talks to your services. Select one with
`-b/--backend` or by exporting `EC_CLI_BACKEND`.

| Backend | Drives | Use it when |
| :--- | :--- | :--- |
| `ARGOCD` *(default)* | An ArgoCD server that reconciles your services. | Services are managed by ArgoCD (GitOps). |
| `K8S` | `kubectl` and `helm` directly against a cluster. | You deploy straight to Kubernetes without ArgoCD. |
| `DEMO` | Built-in sample data — no cluster required. | Trying the tool, demos, and developing the TUI. |

Each backend implements a different slice of the full command set. The next
section is the authoritative matrix.

## Command availability by backend

Commands fall into three slices:

- a **shared slice** available on every backend,
- a **deployment slice** (`deploy`, `delete`) available on `ARGOCD` and `K8S`,
- a **Kubernetes-only slice** for commands that require direct `kubectl`/`helm`
  access.

| Command | ARGOCD | K8S | DEMO | Summary |
| :--- | :---: | :---: | :---: | :--- |
| `env` | ✅ | ✅ | ✅ | List the `EC_*` environment variables and their current values. |
| `list` | ✅ | ✅ | ✅ | List every service available in the repository. |
| `instances` | ✅ | ✅ | ✅ | List all versions of one service in the repository. |
| `ps` | ✅ | ✅ | ✅ | List the services running in the current target. |
| `monitor` | ✅ | ✅ | ✅ | Open the interactive TUI monitor. |
| `logs` | ✅ | ✅ | ✅ | Show current (or previous) logs for a service. |
| `log-history` | ✅ | ✅ | ✅ | Open historical logs for a service. |
| `restart` | ✅ | ✅ | ✅ | Restart a running service. |
| `start` | ✅ | ✅ | ✅ | Start a stopped service. |
| `stop` | ✅ | ✅ | ✅ | Stop a running service. |
| `deploy` | ✅ | ✅ | — | Deploy a service from its source repository. |
| `delete` | ✅ | ✅ | — | Remove a service from the target. |
| `attach` | — | ✅ | — | Attach to the console of a live service. |
| `exec` | — | ✅ | — | Open a bash prompt inside a running container. |
| `deploy-local` | — | ✅ | — | Deploy a local helm chart directly, with a dated beta version. |
| `template` | — | ✅ | — | Render the helm template for a local service definition. |

:::{note}
A few options also vary by backend:
- `deploy` drops `--args` and `--wait` on the `ARGOCD` backend (ArgoCD controls
  rollout and arguments itself).
- `start` and `stop` drop `--commit`/`--no-commit` on the `K8S` backend (there is
  no GitOps repository to commit to).
:::

## Commands

Arguments are positional; options are flags. `SERVICE` below is the name of a
service and supports shell tab-completion.

### Shared commands

These are available on **all** backends.

#### `ec env`

```
$ ec env
```

Print every `EC_*` environment variable `ec` understands and its current value
(or `Not Defined`). A quick way to confirm your configuration — see
[Environment variables](environment-variables.md).

#### `ec list`

```
$ ec list
```

List every service available in the service repository (`--repo`).

#### `ec instances SERVICE`

```
$ ec instances SERVICE
```

List all tagged versions of `SERVICE` found in the repository.

#### `ec ps`

```
$ ec ps [-r/--running-only]
```

List the services in the current target as a table. `-r/--running-only`
restricts the output to services that are currently running.

#### `ec monitor`

```
$ ec monitor [-r/--running-only]
```

Open the interactive TUI monitor. `-r/--running-only` starts it showing only
running services. The monitor can also be served as a web application — see the
[README](https://github.com/epics-containers/edge-containers-cli#monitor).

#### `ec logs SERVICE`

```
$ ec logs SERVICE [-p/--previous]
```

Show the logs for `SERVICE`. `-p/--previous` shows the logs of the previous
instance instead of the current one.

#### `ec log-history SERVICE`

```
$ ec log-history SERVICE
```

Open the historical logs for `SERVICE`. Requires `--log-url`/`EC_LOG_URL`.

#### `ec restart SERVICE`

```
$ ec restart SERVICE
```

Restart `SERVICE`.

(ec-start)=
#### `ec start SERVICE`

```
$ ec start SERVICE [--commit/--no-commit]
```

Start `SERVICE`. `--commit` also records the change in the git repository for an
audit trail (available on `ARGOCD` and `DEMO`; not on `K8S`).

#### `ec stop SERVICE`

```
$ ec stop SERVICE [--commit/--no-commit]
```

Stop `SERVICE`. `--commit` behaves as for [`start`](ec-start).

### Deployment commands (ARGOCD and K8S)

#### `ec deploy SERVICE [VERSION]`

```
$ ec deploy SERVICE [VERSION] [--desc TEXT] [--wait] [-y/--yes] [--args "..."]
```

Add `SERVICE` to the target from its source repository. `VERSION` defaults to the
latest tag. Options:

| Option | Description |
| :--- | :--- |
| `--desc TEXT` | Custom (kebab-case) description label for the service. |
| `--wait` | Wait for the service to become ready. *(K8S only — dropped on ARGOCD.)* |
| `-y`, `--yes` | Skip the confirmation prompt. |
| `--args "..."` | Extra arguments passed to `helm`/`docker`, quoted. *(K8S only — dropped on ARGOCD.)* |

#### `ec delete SERVICE`

```
$ ec delete SERVICE [-y/--yes]
```

Remove `SERVICE` from the target. `-y/--yes` skips the confirmation prompt.

### Kubernetes-only commands (K8S)

#### `ec attach SERVICE`

```
$ ec attach SERVICE
```

Attach to the console of a live service.

#### `ec exec SERVICE`

```
$ ec exec SERVICE
```

Open an interactive bash prompt inside the running container for `SERVICE`.

#### `ec deploy-local PATH`

```
$ ec deploy-local PATH [-y/--yes] [--args "..."]
```

Deploy a local service definition (a helm chart folder) directly to the cluster
with a dated beta version. `PATH` must be an existing directory. `--args` passes
extra quoted arguments to `helm`.

#### `ec template PATH`

```
$ ec template PATH [--args "..."]
```

Render and print the helm template generated from a local service definition at
`PATH`. Useful for inspecting what `deploy-local` would apply.
