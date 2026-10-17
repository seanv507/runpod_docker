#!/bin/bash
# Container CMD: starts the base image services (Jupyter/SSH) in the background,
# then performs optional workspace setup driven by environment variables
# (normally supplied by launch.py from a preset). Every step is skipped when
# its variable is unset, so the image also works as a plain pod.
#
#   GITHUB_SSH / GITHUB_SSH_PUB  private/public deploy key for cloning private repos
#   REPOS              space-separated "git_url#branch" entries (branch optional),
#                      cloned into $CODE_DIR (skipped if the directory already exists)
#   EDITABLE_INSTALLS  space-separated directories (relative to $CODE_DIR) to `uv pip install -e`
#   PIP_PACKAGES       space-separated packages to `uv pip install`
#   HF_DATASETS        space-separated Hugging Face dataset ids, downloaded to $DATA_DIR/<name>
#   WANDB_API_KEY      if set, `wandb login`
#   EXTRA_DOWNLOADS    space-separated URLs fetched into $CODE_DIR and made executable
#   POST_SETUP_CMD     command run (via bash -c) in $CODE_DIR after everything else
#   CODE_DIR / DATA_DIR  default /workspace/code and /workspace/data

# Start base image services (Jupyter/SSH) in background
/start.sh &

# Wait a moment for services to start
sleep 2

CODE_DIR=${CODE_DIR:-/workspace/code}
DATA_DIR=${DATA_DIR:-/workspace/data}
mkdir -p "$CODE_DIR" "$DATA_DIR" ~/.ssh
set -o xtrace

if [[ -n "$GITHUB_SSH" ]]; then
    set +o xtrace  # don't echo the key
    echo "$GITHUB_SSH" > ~/.ssh/github_ssh && chmod 600 ~/.ssh/github_ssh
    echo "$GITHUB_SSH_PUB" > ~/.ssh/github_ssh.pub && chmod 600 ~/.ssh/github_ssh.pub
    unset GITHUB_SSH
    set -o xtrace

    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/github_ssh
    cat > ~/.ssh/config << EOF
Host github.com
    User git
    IdentityFile ~/.ssh/github_ssh
EOF
    chmod 600 ~/.ssh/config

    # Source - https://stackoverflow.com/a/47708298
    # Posted by VonC, modified by community. See post 'Timeline' for change history
    # Retrieved 2026-06-14, License - CC BY-SA 4.0
    ssh-keygen -R github.com
    curl -L https://api.github.com/meta | jq -r '.ssh_keys | .[]' | sed -e 's/^/github.com /' >> ~/.ssh/known_hosts
fi

cd "$CODE_DIR" || exit 1

for entry in $REPOS; do
    url=${entry%%#*}
    branch=""
    [[ "$entry" == *#* ]] && branch=${entry#*#}
    dir=$(basename "$url" .git)
    if [[ -d "$dir" ]]; then
        echo "$dir already exists, skipping clone"
    elif [[ -n "$branch" ]]; then
        git clone -b "$branch" "$url"
    else
        git clone "$url"
    fi
done

for pkg_dir in $EDITABLE_INSTALLS; do
    uv pip install -e "$pkg_dir"
done

if [[ -n "$PIP_PACKAGES" ]]; then
    # shellcheck disable=SC2086
    uv pip install $PIP_PACKAGES
fi

for dataset in $HF_DATASETS; do
    hf download --repo-type dataset "$dataset" --local-dir "$DATA_DIR/${dataset##*/}"
done

if [[ -n "$WANDB_API_KEY" ]]; then
    wandb login
    # reads WANDB_API_KEY from the environment
fi

for download_url in $EXTRA_DOWNLOADS; do
    wget -N "$download_url"
    chmod +x "$(basename "$download_url")"
done

if [[ -n "$POST_SETUP_CMD" ]]; then
    bash -c "$POST_SETUP_CMD"
fi

set +o xtrace
echo "Setup finished."

# Wait for background processes
wait
