"""Launch and manage RunPod pods running the image built from Dockerfile.uv.

Examples:
    uv run launch.py create --preset presets/fcn.yaml --dry-run
    uv run launch.py create --preset presets/fcn.yaml --gpu "NVIDIA A40" --env HF_DATASETS=
    uv run launch.py list
    uv run launch.py list-gpus
    uv run launch.py stop <pod_id>
    uv run launch.py terminate <pod_id>

Requires RUNPOD_API_KEY in the environment (except for --dry-run).
"""

import argparse
import json
import os
import sys

import yaml

POD_DEFAULTS = {
    "name": "runpod-docker",
    "image": None,
    "gpu": "NVIDIA GeForce RTX 4090",
    "gpu_count": 1,
    "cloud_type": "SECURE",
    "volume_gb": 50,
    "container_disk_gb": 30,
    "network_volume_id": None,
    "data_center_id": None,
    "allowed_cuda_versions": None,
    "ports": "8888/http,22/tcp",
}


def load_preset(path):
    if path is None:
        return {}, {}
    with open(path) as f:
        preset = yaml.safe_load(f) or {}
    return preset.get("pod", {}), preset.get("env", {})


def parse_env_overrides(items):
    env = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep:
            sys.exit(f"--env expects KEY=VALUE, got {item!r}")
        env[key] = value
    return env


def build_pod_request(args):
    pod_preset, env = load_preset(args.preset)
    pod = {**POD_DEFAULTS, **pod_preset}
    for key in POD_DEFAULTS:
        value = getattr(args, key, None)
        if value is not None:
            pod[key] = value
    if not pod["image"]:
        sys.exit("No image given: set pod.image in the preset or pass --image")

    env = {k: str(v) for k, v in env.items()}
    env.update(parse_env_overrides(args.env))
    env = {k: v for k, v in env.items() if v != ""}  # --env KEY= removes a preset entry

    return dict(
        name=pod["name"],
        image_name=pod["image"],
        gpu_type_id=pod["gpu"],
        gpu_count=pod["gpu_count"],
        cloud_type=pod["cloud_type"],
        volume_in_gb=pod["volume_gb"] if not pod["network_volume_id"] else 0,
        container_disk_in_gb=pod["container_disk_gb"],
        network_volume_id=pod["network_volume_id"],
        data_center_id=pod["data_center_id"],
        allowed_cuda_versions=pod["allowed_cuda_versions"],
        ports=pod["ports"],
        volume_mount_path="/workspace",
        support_public_ip=True,
        start_ssh=True,
        env=env,
    )


def connect():
    import runpod

    api_key = os.environ.get("RUNPOD_API_KEY")
    if not api_key:
        sys.exit("RUNPOD_API_KEY is not set")
    runpod.api_key = api_key
    return runpod


def cmd_create(args):
    request = build_pod_request(args)
    if args.dry_run:
        print(json.dumps(request, indent=2))
        return
    runpod = connect()
    pod = runpod.create_pod(**request)
    pod_id = pod["id"]
    print(f"Created pod {pod_id} ({request['gpu_count']}x {request['gpu_type_id']}, {request['image_name']})")
    print(f"  console:  https://console.runpod.io/pods?id={pod_id}")
    print(f"  jupyter:  https://{pod_id}-8888.proxy.runpod.net")
    print(f"  ssh:      ssh {pod_id}@ssh.runpod.io  (or see 'Connect' in the console)")


def cmd_list(args):
    runpod = connect()
    for pod in runpod.get_pods():
        machine = pod.get("machine") or {}
        print(
            f"{pod['id']}  {pod.get('desiredStatus', ''):<10} {pod.get('name', ''):<20} "
            f"{machine.get('gpuDisplayName', '')}  ${pod.get('costPerHr', '?')}/hr  {pod.get('imageName', '')}"
        )


def cmd_list_gpus(args):
    runpod = connect()
    for gpu in sorted(runpod.get_gpus(), key=lambda g: g.get("memoryInGb", 0)):
        print(f"{gpu['id']:<40} {gpu.get('memoryInGb', '?'):>4} GB  {gpu.get('displayName', '')}")


def cmd_stop(args):
    connect().stop_pod(args.pod_id)
    print(f"Stopped {args.pod_id}")


def cmd_terminate(args):
    connect().terminate_pod(args.pod_id)
    print(f"Terminated {args.pod_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a pod")
    create.add_argument("--preset", help="YAML preset with `pod` and `env` sections")
    create.add_argument("--name")
    create.add_argument("--image", help="docker image, e.g. seanv507/fcn_runpod:0.0.8")
    create.add_argument("--gpu", help="GPU type id (see list-gpus)")
    create.add_argument("--gpu-count", dest="gpu_count", type=int)
    create.add_argument("--cloud-type", dest="cloud_type", choices=["SECURE", "COMMUNITY", "ALL"])
    create.add_argument("--volume-gb", dest="volume_gb", type=int, help="pod volume mounted at /workspace")
    create.add_argument("--container-disk-gb", dest="container_disk_gb", type=int)
    create.add_argument("--network-volume-id", dest="network_volume_id", help="use a network volume instead of a pod volume")
    create.add_argument("--data-center-id", dest="data_center_id")
    create.add_argument("--env", action="append", default=[], metavar="KEY=VALUE",
                        help="override/add a pod env var (repeatable); KEY= removes it")
    create.add_argument("--dry-run", action="store_true", help="print the request without creating a pod")
    create.set_defaults(func=cmd_create)

    sub.add_parser("list", help="list your pods").set_defaults(func=cmd_list)
    sub.add_parser("list-gpus", help="list available GPU types").set_defaults(func=cmd_list_gpus)
    for name, func in [("stop", cmd_stop), ("terminate", cmd_terminate)]:
        p = sub.add_parser(name, help=f"{name} a pod")
        p.add_argument("pod_id")
        p.set_defaults(func=func)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
