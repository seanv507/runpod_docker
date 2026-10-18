# runpod_docker

Docker image and launcher for RunPod GPU pods. Extracted from the FCN repo (`~/projects/FCN`), which no longer contains any Docker files. See README.md for user-facing docs.

## How the pieces fit
- `Dockerfile.uv`: extends `seanv507/pytorch:1.0.7-cu1300-torch2130-ubuntu2404` (CUDA 13). Installs uv, creates a venv at `/opt/.venvs/ML` (on PATH), installs `requirements.txt`, builds XGBoost with CUDA from the `seanv507/xgboost` fork (build args `XGBOOST_REPO`/`XGBOOST_BRANCH`, default `cat_order_smooth`) and installs it into the venv, and sets `CMD` to `/app/run.sh`.
- `run.sh`: runs at container start. It starts the base image's `/start.sh` (Jupyter/SSH) in the background, then does workspace setup in `/workspace/code` and `/workspace/data`, all driven by env vars. Each step is skipped when its variable is unset. Variables: `GITHUB_SSH`/`GITHUB_SSH_PUB`, `REPOS` (`url#branch`; `#` because branches may contain `/`), `EDITABLE_INSTALLS`, `PIP_PACKAGES`, `HF_DATASETS`, `WANDB_API_KEY`, `EXTRA_DOWNLOADS`, `POST_SETUP_CMD`, `CODE_DIR`/`DATA_DIR`. Clones are skipped when the folder exists, so restarts on a persistent volume are safe.
- `presets/*.yaml`: a `pod:` section holds the defaults for `launch.py` flags, and an `env:` section holds the pod env vars for `run.sh`. Secrets are always RunPod secret refs (`{{ RUNPOD_SECRET_<name> }}`), never plaintext. `fcn.yaml` is the FCN/FuxiCTR Criteo setup.
- `launch.py`: uses the RunPod Python SDK (`runpod`). Subcommands are `create`, `list`, `list-gpus`, `stop` and `terminate`. CLI flags override the preset, and `--env KEY=VALUE` adds or overrides an env var (`KEY=` removes it). Needs `RUNPOD_API_KEY`, except for `--dry-run`.
- `reference/start.sh`: a copy of the base image's `/start.sh`, for reference only. Don't edit it.

## Commands
```bash
uv sync                                                        # launcher deps (runpod, pyyaml)
uv run launch.py create --preset presets/fcn.yaml --dry-run    # safe: prints request only
bash -n run.sh                                                 # syntax check
docker build --platform linux/amd64 -f Dockerfile.uv -t fcn_runpod:<tag> .
docker tag fcn_runpod:<tag> seanv507/fcn_runpod:<tag> && docker push seanv507/fcn_runpod:<tag>
```

## Conventions / cautions
- Creating a pod (`launch.py create` without `--dry-run`) costs money. Ask before running it, and before `docker push`.
- Docker builds are slow because the base image is large. Ask before building.
- After pushing a new image tag, update `pod.image` in the presets.
- `.dockerignore` excludes everything except `requirements.txt` and `run.sh`. Whitelist any new file the Dockerfile `COPY`s.
- Keep project-specific setup in presets, not in `run.sh`. If a new setup step is needed, add it to `run.sh` as a generic env-var-gated step.

## Status (2026-10-18)
The repo is on GitHub at `seanv507/runpod_docker` (remote `origin`). The current image on Docker Hub is `seanv507/fcn_runpod:0.1.1`. It has the CUDA XGBoost build from the fork, and its venv can see the base image's torch. 0.1.0 has the same XGBoost build, but `import torch` fails in its venv and it is about 4 GB bigger (leftover uv cache). 0.0.9 has the PyPI xgboost, and 0.0.8 and earlier have the old FCN-specific `run.sh`. The RunPod secrets `github_ssh`, `github_ssh_pub` and `wandb_key` must exist before launching.
