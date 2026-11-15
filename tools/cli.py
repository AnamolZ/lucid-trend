"""Command-line interface client for managing and monitoring the LucidTrend server."""

import os
import sys
import re
import argparse
import requests
import json
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SERVER = os.getenv("SERVER_URL", "http://localhost:8000")

def resolve_api_key(passed_key: str = None) -> str:
    """Prompts the user interactively for the server API key if not supplied via command line."""
    if passed_key and str(passed_key).strip():
        return str(passed_key).strip()

    # Check if input was piped in non-interactive environment
    if not sys.stdin.isatty():
        try:
            line = sys.stdin.readline().strip()
            if line:
                return line
        except Exception:
            pass

    try:
        import getpass
        entered = getpass.getpass("🔑 Enter Server API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[ABORTED] Authentication cancelled.")
        sys.exit(1)
    except Exception:
        entered = input("🔑 Enter Server API Key: ").strip()

    if not entered:
        print("\n[AUTHENTICATION ERROR] API key cannot be empty.\n")
        sys.exit(1)

    return entered

def check_server_connection(server_url: str, api_key: str) -> dict:
    """Verifies that the server is online and authenticates before running commands."""
    endpoint = f"{server_url.rstrip('/')}/api/v1/status"
    try:
        response = requests.get(
            endpoint,
            headers={"X-API-Key": api_key},
            timeout=5
        )
        if response.status_code == 401:
            print(f"\n[AUTHENTICATION ERROR] Access Denied: Invalid API key provided.")
            print("Please verify the key matches the server's API_SECRET_KEY configuration.\n")
            sys.exit(1)
        elif response.status_code != 200:
            print(f"\n[SERVER ERROR] Server returned HTTP {response.status_code}: {response.text}\n")
            sys.exit(1)
        return response.json()
    except requests.exceptions.ConnectionError:
        print("\n" + "=" * 65)
        print(" [CONNECTION FAILED] Server is not reachable")
        print("=" * 65)
        print(f" Target Endpoint: {server_url}")
        print("\n The CLI requires an active LucidTrend server to execute commands.")
        print(" Please ensure the server is running (natively or in Docker):")
        print("   - Native:  uv run python main.py")
        print("   - Docker:  docker-compose up -d")
        print("=" * 65 + "\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error connecting to server: {e}\n")
        sys.exit(1)

def handle_status(server_url: str, api_key: str, args):
    """Fetches and displays live server health metrics, configuration status, and active schedule."""
    status_data = check_server_connection(server_url, api_key)
    print("\n" + "=" * 65)
    print(" LucidTrend Server Status: CONNECTED & ONLINE")
    print("=" * 65)
    for k, v in status_data.items():
        if k == "scheduled_daily_runs" and isinstance(v, list):
            print(f"  {k:<30}: {', '.join(v)} Asia/Kathmandu (12h gap)")
        else:
            print(f"  {k:<30}: {v}")
    print("=" * 65 + "\n")

def handle_pipeline(server_url: str, api_key: str, args):
    """Dispatches a modular pipeline execution request with optional module exclusion and live schedule reshuffle."""
    check_server_connection(server_url, api_key)

    with_db = True
    with_email = True
    with_image = True

    if hasattr(args, "without") and args.without:
        without_tokens = [t.strip().lower() for t in args.without.split(",") if t.strip()]
        if "db" in without_tokens or "database" in without_tokens:
            with_db = False
        if "email" in without_tokens or "newsletter" in without_tokens:
            with_email = False
        if "image" in without_tokens or "images" in without_tokens or "imagegeneration" in without_tokens:
            with_image = False

    if hasattr(args, "with_flags") and args.with_flags:
        with_tokens = [t.strip().lower() for t in args.with_flags.split(",") if t.strip()]
        if "db" in with_tokens or "database" in with_tokens:
            with_db = True
        if "email" in with_tokens or "newsletter" in with_tokens:
            with_email = True
        if "image" in with_tokens or "images" in with_tokens or "imagegeneration" in with_tokens:
            with_image = True

    print("\n" + "=" * 65)
    print(" [LucidTrend CLI] Dispatching Pipeline Command")
    print(f"  - Database Writing : {'ENABLED' if with_db else 'DISABLED'}")
    print(f"  - Email Dispatch   : {'ENABLED' if with_email else 'DISABLED'}")
    print(f"  - Image Synthesis  : {'ENABLED' if with_image else 'DISABLED'}")
    print("=" * 65)
    print("Querying intelligence scout... Please wait...\n")

    payload = {
        "with_db": with_db,
        "with_email": with_email,
        "with_image": with_image,
        "research_prompt": args.prompt if hasattr(args, "prompt") else None
    }

    resp = requests.post(
        f"{server_url.rstrip('/')}/api/v1/pipeline/run",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=360
    )

    if resp.status_code != 200:
        print(f"[ERROR] Pipeline run failed with code {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    articles = data.get("articles", [])
    print(f"Successfully synthesized {len(articles)} articles!\n")

    for idx, art in enumerate(articles, start=1):
        print(f"--- Article #{idx} ---")
        print(f"Title: {art.get('title')}")
        print(f"Category: {art.get('category')}")
        print(f"Summary: {art.get('description')}")
        print(f"\n[FLUX.1 IMAGE GENERATION PROMPT]:")
        print(f"  -> \"{art.get('image_prompt')}\"")
        print("-" * 65 + "\n")

    reshuffled = data.get("reshuffled_schedule")

    print("Execution Summary:")
    print(f"  - Articles Created  : {data.get('articles_count')}")
    print(f"  - MongoDB Inserted  : {data.get('database_inserted')}")
    print(f"  - Newsletter Sent   : {data.get('email_dispatched')}")
    print(f"  - Images Queued     : {data.get('images_queued')}")
    if reshuffled and isinstance(reshuffled, list):
        print(f"  - Schedule Reshuffle: Set to {reshuffled[0]} and {reshuffled[1]} Asia/Kathmandu (12h gap)")
    print("=" * 65 + "\n")

def handle_generate_image(server_url: str, api_key: str, args):
    """Requests on-demand image synthesis and writes the result to local storage."""
    check_server_connection(server_url, api_key)

    prompt = args.prompt
    title = args.title

    if not prompt and not title:
        print("[ERROR] Please provide either --prompt or --title to generate an image.")
        sys.exit(1)

    print("\n" + "=" * 65)
    print(" [LucidTrend CLI] Generating Image on Remote/Local Server")
    if prompt:
        print(f"[IMAGE PROMPT]:\n  -> \"{prompt}\"")
    if title:
        print(f"[TITLE]:\n  -> \"{title}\"")
    print("=" * 65)
    print("Synthesizing image with FLUX.1 (cycling 4 keys with 5-min retry ladder)... Please wait...\n")

    payload = {"prompt": prompt, "title": title}
    resp = requests.post(
        f"{server_url.rstrip('/')}/api/v1/image/generate",
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=360
    )

    if resp.status_code != 200:
        print(f"[ERROR] Image generation failed with code {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    prompt_used = data.get("prompt_used")
    filename = data.get("filename", "generated_image.png")
    download_url = data.get("download_url")

    output_path = args.output if hasattr(args, "output") and args.output else os.path.join(os.getcwd(), filename)

    print(f"[PROMPT USED BY MODEL]:\n  -> \"{prompt_used}\"\n")

    if download_url:
        img_resp = requests.get(f"{server_url.rstrip('/')}{download_url}", timeout=30)
        if img_resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(img_resp.content)
            print("=" * 65)
            print(f"[SUCCESS] Image generated and saved to current directory:")
            print(f"  -> File: {output_path} ({len(img_resp.content):,} bytes)")
            print(f"  -> Server temp file: {data.get('temp_file_path')}")
            print("=" * 65 + "\n")
            return

    if data.get("image_data_uri"):
        raw_b64 = data["image_data_uri"].split(",", 1)[1]
        import base64
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(raw_b64))
        print(f"[SUCCESS] Image generated and saved to: {output_path}\n")

def handle_reshuffle(server_url: str, api_key: str, args):
    """Requests the server to dynamically reshuffle the daily 12-hour schedule."""
    check_server_connection(server_url, api_key)
    resp = requests.post(
        f"{server_url.rstrip('/')}/api/v1/schedule/reshuffle",
        headers={"X-API-Key": api_key},
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        runs = data.get("scheduled_daily_runs", [])
        print("\n" + "=" * 65)
        print(" [SUCCESS] Daily Schedule Reshuffled on Server")
        print("=" * 65)
        print(f"  New Daily Run Times : {', '.join(runs)} Asia/Kathmandu")
        print(f"  Schedule Interval   : {data.get('schedule_interval', '12 hours (2 runs per day)')}")
        print("=" * 65 + "\n")
    else:
        print(f"\n[ERROR] Reshuffle failed with code {resp.status_code}: {resp.text}\n")

def handle_cleanup_temp(server_url: str, api_key: str, args):
    """Triggers an immediate cleanup of the server's temporary files."""
    check_server_connection(server_url, api_key)
    resp = requests.post(
        f"{server_url.rstrip('/')}/api/v1/cleanup/temp",
        headers={"X-API-Key": api_key},
        timeout=10
    )
    if resp.status_code == 200:
        purged = resp.json().get("files_purged", 0)
        print(f"\n[SUCCESS] Server temp directory purged: {purged} temporary files removed.\n")
    else:
        print(f"\n[ERROR] Cleanup failed: {resp.text}\n")

def handle_push_test(server_url: str, api_key: str, args):
    """Sends a test mobile push notification via the server."""
    check_server_connection(server_url, api_key)
    endpoint = f"{server_url.rstrip('/')}/api/v1/push/test"
    payload = {
        "title": getattr(args, "title", None) or "NewsPluk | Push Notification Test",
        "body": getattr(args, "body", None) or "Firebase background push delivered successfully!",
        "post_id": getattr(args, "post_id", None) or "test-push",
        "topic": getattr(args, "topic", None) or "all_news"
    }
    print(f"\n[CLI] Dispatching test push notification to topic '{payload['topic']}'...")
    resp = requests.post(endpoint, json=payload, headers={"X-API-Key": api_key}, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        print("\n" + "=" * 65)
        print(" [SUCCESS] Firebase Mobile Push Dispatched")
        print("=" * 65)
        print(f"  Topic    : {data.get('topic')}")
        print(f"  Title    : {data.get('title')}")
        print(f"  Post ID  : {data.get('post_id')}")
        print("=" * 65 + "\n")
    else:
        print(f"\n[ERROR] Push dispatch failed ({resp.status_code}): {resp.text}\n")
        sys.exit(1)

def handle_rotate_key(server_url: str, args):
    """Regenerates a new server API key using master password authentication."""
    master_pwd = getattr(args, "master_password", None)
    if not master_pwd:
        if sys.stdin.isatty():
            try:
                import getpass
                master_pwd = getpass.getpass("🔑 Enter Master Password: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[ABORTED] Key rotation cancelled.")
                sys.exit(1)
        else:
            line = sys.stdin.readline()
            master_pwd = line.strip() if line else ""

    if not master_pwd:
        print("\n[ERROR] Master password cannot be empty.\n")
        sys.exit(1)

    try:
        resp = requests.post(
            f"{server_url.rstrip('/')}/api/v1/auth/rotate-key",
            json={"master_password": master_pwd},
            timeout=10
        )
    except requests.exceptions.ConnectionError:
        print("\n" + "=" * 65)
        print(" [CONNECTION FAILED] Server is not reachable")
        print("=" * 65)
        print(f" Target Endpoint: {server_url}")
        print("\n Key rotation requires an active LucidTrend server.")
        print(" Please ensure the server is running (natively or in Docker):")
        print("   - Native:  uv run python main.py")
        print("   - Docker:  docker-compose up -d")
        print("=" * 65 + "\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error connecting to server: {e}\n")
        sys.exit(1)

    if resp.status_code == 200:
        data = resp.json()
        new_key = data.get("new_api_key")

        # Update local .env file if present
        local_env = os.path.join(os.getcwd(), ".env")
        if os.path.exists(local_env):
            try:
                with open(local_env, "r", encoding="utf-8") as f:
                    content = f.read()
                if re.search(r"^API_SECRET_KEY=.*", content, flags=re.MULTILINE):
                    content = re.sub(r"^API_SECRET_KEY=.*", f"API_SECRET_KEY={new_key}", content, flags=re.MULTILINE)
                else:
                    content += f"\nAPI_SECRET_KEY={new_key}\n"
                with open(local_env, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass

        print("\n" + "=" * 65)
        print(" [SUCCESS] Server API Key Regenerated & Rotated")
        print("=" * 65)
        print("  Old Key Status : Inactivated & Revoked Immediately")
        print(f"  New API Key    : {new_key}")
        print("=" * 65)
        print("  Notice:")
        print("  - The previous API key has been revoked and will no longer work.")
        print("  - The new API key is active on the server and saved to .env.")
        print("  - Use this new API key for all subsequent CLI commands.\n")
    elif resp.status_code == 403:
        print("\n[AUTHENTICATION ERROR] Access Denied: Invalid master password.")
        print("Key rotation rejected by the server.\n")
        sys.exit(1)
    else:
        print(f"\n[ERROR] Key rotation failed ({resp.status_code}): {resp.text}\n")
        sys.exit(1)

def main():
    """Parses CLI subcommands and dispatches execution to dedicated command handlers."""
    parser = argparse.ArgumentParser(
        description="LucidTrend Autonomous System - Interactive CLI & Server Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run cli.py status
  uv run cli.py pipeline --without email,db,image
  uv run cli.py pipeline --with db,image --without email
  uv run cli.py generate-image --prompt "Futuristic quantum neural network, 16:9"
  uv run cli.py reshuffle
  uv run cli.py rotate-key
  uv run cli.py cleanup-temp
        """
    )
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--key", default=None, help="API Secret Key (if omitted, prompted interactively)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Check server health, key status, and active schedule")
    status_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    status_parser.add_argument("--key", default=argparse.SUPPRESS, help="API Secret Key")

    pipeline_parser = subparsers.add_parser("pipeline", help="Execute on-demand post generation and reshuffle daily schedule")
    pipeline_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    pipeline_parser.add_argument("--key", default=argparse.SUPPRESS, help="API Secret Key")
    pipeline_parser.add_argument("--without", help="Comma-separated modules to skip (e.g. email,db,image)")
    pipeline_parser.add_argument("--with", dest="with_flags", help="Comma-separated modules to force enable (e.g. db,image)")
    pipeline_parser.add_argument("--prompt", help="Custom research prompt")

    img_parser = subparsers.add_parser("generate-image", help="Generate an isolated image on-demand")
    img_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    img_parser.add_argument("--key", default=argparse.SUPPRESS, help="API Secret Key")
    img_parser.add_argument("--prompt", help="Text-to-image prompt for FLUX.1")
    img_parser.add_argument("--title", help="Article headline to automatically craft prompt from")
    img_parser.add_argument("--output", help="Custom output filepath on current machine")

    reshuffle_parser = subparsers.add_parser("reshuffle", help="Reshuffle the daily pipeline schedule (2 runs per day, 12h gap)")
    reshuffle_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    reshuffle_parser.add_argument("--key", default=argparse.SUPPRESS, help="API Secret Key")

    rotate_parser = subparsers.add_parser("rotate-key", help="Regenerate new API key via master password (invalidates old key)")
    rotate_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    rotate_parser.add_argument("--master-password", help="Master password for key rotation")

    regen_parser = subparsers.add_parser("regenerate-key", help="Alias for rotate-key")
    regen_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    regen_parser.add_argument("--master-password", help="Master password for key rotation")

    cleanup_parser = subparsers.add_parser("cleanup-temp", help="Purge server temporary image folder")
    cleanup_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    cleanup_parser.add_argument("--key", default=argparse.SUPPRESS, help="API Secret Key")

    push_parser = subparsers.add_parser("push-test", help="Broadcast a test push notification to mobile app via Firebase")
    push_parser.add_argument("--title", help="Notification title")
    push_parser.add_argument("--body", help="Notification message body")
    push_parser.add_argument("--post-id", help="Article ID for deep-linking")
    push_parser.add_argument("--topic", default="all_news", help="Firebase topic (default: all_news)")
    push_parser.add_argument("--server", default=argparse.SUPPRESS, help="Server URL")
    push_parser.add_argument("--key", default=argparse.SUPPRESS, help="API Secret Key")

    args = parser.parse_args()

    server_url = getattr(args, "server", DEFAULT_SERVER)

    if args.command in ["rotate-key", "regenerate-key"]:
        handle_rotate_key(server_url, args)
        return

    raw_key = getattr(args, "key", None)
    api_key = resolve_api_key(raw_key)

    if args.command == "status":
        handle_status(server_url, api_key, args)
    elif args.command == "pipeline":
        handle_pipeline(server_url, api_key, args)
    elif args.command == "generate-image":
        handle_generate_image(server_url, api_key, args)
    elif args.command == "reshuffle":
        handle_reshuffle(server_url, api_key, args)
    elif args.command == "cleanup-temp":
        handle_cleanup_temp(server_url, api_key, args)
    elif args.command == "push-test":
        handle_push_test(server_url, api_key, args)

if __name__ == "__main__":
    main()
