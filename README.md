# runpod_docker

A Docker image and launcher for RunPod GPU pods. The image extends a RunPod PyTorch base image, so Jupyter, SSH and CUDA setup work as usual. It adds a uv virtualenv with the packages in `requirements.txt`. When the container starts, `run.sh` sets up the workspace: it clones repos, installs packages and downloads datasets, all driven by pod environment variables. Presets in `presets/` describe each project's setup, and `launch.py` creates pods with the RunPod Python SDK.

## Files

- `Dockerfile.uv`: the image. Base `seanv507/pytorch:1.0.7-cu1300-torch2130-ubuntu2404` (CUDA 13), with uv and a venv at `/opt/.venvs/ML` on `PATH`.
- `requirements.txt`: Python packages baked into the image.
- `run.sh`: the container `CMD`. It starts `/start.sh` (Jupyter/SSH) in the background, then runs the env-driven setup.
- `launch.py`: creates, lists, stops and terminates pods.
- `presets/*.yaml`: per-project pod settings and env vars. `fcn.yaml` is the FCN/FuxiCTR Criteo setup.
- `reference/start.sh`: a copy of the base image's `/start.sh`, for reference.

## Build and push

```bash
docker build --platform linux/amd64 -f Dockerfile.uv -t fcn_runpod:0.0.9 .
docker tag fcn_runpod:0.0.9 seanv507/fcn_runpod:0.0.9
docker login
docker push seanv507/fcn_runpod:0.0.9
```

After pushing a new tag, update `pod.image` in the preset, or pass `--image`.

Test locally. With no env vars set, every setup step is skipped:
```bash
docker run --rm -it --platform linux/amd64 fcn_runpod:0.0.9
docker run --rm -it --platform linux/amd64 fcn_runpod:0.0.9 /bin/bash
```

## run.sh environment variables

Each step runs only when its variable is set. Lists are space-separated.

| Variable | Effect |
|---|---|
| `GITHUB_SSH`, `GITHUB_SSH_PUB` | SSH key for cloning private GitHub repos (added to ssh-agent and `~/.ssh/config`) |
| `REPOS` | `git_url#branch` entries (the branch is optional), cloned into `$CODE_DIR`; a repo whose directory already exists is skipped |
| `EDITABLE_INSTALLS` | directories in `$CODE_DIR`, each installed with `uv pip install -e` |
| `PIP_PACKAGES` | packages to `uv pip install` |
| `HF_DATASETS` | Hugging Face dataset ids, each downloaded to `$DATA_DIR/<name>` |
| `WANDB_API_KEY` | `wandb login` |
| `EXTRA_DOWNLOADS` | URLs fetched into `$CODE_DIR` with `wget` and made executable |
| `POST_SETUP_CMD` | a final command, run with `bash -c` in `$CODE_DIR` |
| `CODE_DIR`, `DATA_DIR` | defaults are `/workspace/code` and `/workspace/data` |

## Launching pods

```bash
uv sync
export RUNPOD_API_KEY=...

uv run launch.py create --preset presets/fcn.yaml --dry-run   # print the request only
uv run launch.py create --preset presets/fcn.yaml
uv run launch.py create --preset presets/fcn.yaml --gpu "NVIDIA A40" --env HF_DATASETS=   # override GPU, skip the dataset download
uv run launch.py list-gpus
uv run launch.py list
uv run launch.py stop <pod_id>
uv run launch.py terminate <pod_id>
```

Command-line flags override the preset's `pod` section. `--env KEY=VALUE` adds or overrides an env var, and `--env KEY=` removes it.

### Secrets

Presets refer to secrets as RunPod secrets, for example `GITHUB_SSH: "{{ RUNPOD_SECRET_github_ssh }}"`, so the values never leave RunPod. Create these secrets in the RunPod console (Settings → Secrets) before you launch:

- `github_ssh`, `github_ssh_pub`: a GitHub deploy key, or a personal SSH key with access to the repos
- `wandb_key`: a Weights & Biases API key

## Adding a project

Copy `presets/fcn.yaml`, then change `pod.image` and the `env` entries. If the project needs extra system or Python packages baked into the image, add them to `Dockerfile.uv` or `requirements.txt` and build a new tag.
