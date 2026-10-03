import os
import sys
import argparse
import requests
import json
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SERVER = os.getenv("SERVER_URL", "http://localhost:8000")
DEFAULT_KEY = os.getenv("API_SECRET_KEY", "lt_sec_9f82d1c3a7e54b60a12e847c5d9f3b1a")

def check_server_connection(server_url: str, api_key: str):
    """
    Mandatory connection check:
    Verifies that the server is alive and that the API key is authorized.
    Terminates execution if connection cannot be established.
    """
    endpoint = f"{server_url.rstrip('/')}/api/v1/status"
    try:
        response = requests.get(
            endpoint,
            headers={"X-API-Key": api_key},
            timeout=5
        )
        if response.status_code == 401:
            print(f"\n[AUTHENTICATION ERROR] Access Denied: Invalid API key provided.")
            print("Ensure API_SECRET_KEY matches the server configuration.\n")
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
    status_data = check_server_connection(server_url, api_key)
    print("\n" + "=" * 65)
    print(" LucidTrend Server Status: CONNECTED & ONLINE")
    print("=" * 65)
    for k, v in status_data.items():
        print(f"  {k:<30}: {v}")
    print("=" * 65 + "\n")

def handle_pipeline(server_url: str, api_key: str, args):
    # Mandatory connection check first
    check_server_connection(server_url, api_key)

    with_db = True
    with_email = True
    with_image = True

    # Parse --without flags
    if args.without:
        without_tokens = [t.strip().lower() for t in args.without.split(",") if t.strip()]
        if "db" in without_tokens or "database" in without_tokens:
            with_db = False
        if "email" in without_tokens or "newsletter" in without_tokens:
            with_email = False
        if "image" in without_tokens or "images" in without_tokens or "imagegeneration" in without_tokens:
            with_image = False

    # Parse --with flags
    if args.with_flags:
        with_tokens = [t.strip().lower() for t in args.with_flags.split(",") if t.strip()]
        # If --with is explicitly specified, enable matching ones
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
        timeout=180
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

    print("Execution Summary:")
    print(f"  - Articles Created  : {data.get('articles_count')}")
    print(f"  - MongoDB Inserted  : {data.get('database_inserted')}")
    print(f"  - Newsletter Sent   : {data.get('email_dispatched')}")
    print(f"  - Images Queued     : {data.get('images_queued')}")
    print("=" * 65 + "\n")

def handle_generate_image(server_url: str, api_key: str, args):
    # Mandatory connection check first
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

    # Destination on current drive / directory where CLI was executed
    output_path = args.output if args.output else os.path.join(os.getcwd(), filename)

    print(f"[PROMPT USED BY MODEL]:\n  -> \"{prompt_used}\"\n")

    # Download binary from server static temp endpoint or decode base64
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

    # Fallback to base64 if download_url failed
    if data.get("image_data_uri"):
        raw_b64 = data["image_data_uri"].split(",", 1)[1]
        import base64
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(raw_b64))
        print(f"[SUCCESS] Image generated and saved to: {output_path}\n")

def handle_cleanup_temp(server_url: str, api_key: str, args):
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

def main():
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    parent_parser.add_argument("--key", default=DEFAULT_KEY, help="API Secret Key for server authentication")

    parser = argparse.ArgumentParser(
        description="LucidTrend Autonomous System - Interactive CLI & Server Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent_parser],
        epilog="""
Examples:
  uv run cli.py status
  uv run cli.py pipeline --without email,db,image
  uv run cli.py pipeline --with db,image --without email
  uv run cli.py generate-image --prompt "Futuristic quantum neural network, 16:9"
  uv run cli.py generate-image --title "AI Leading the Software Industry"
  uv run cli.py cleanup-temp
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: status
    subparsers.add_parser("status", parents=[parent_parser], help="Check server health and connectivity")

    # Subcommand: pipeline
    pipeline_parser = subparsers.add_parser("pipeline", parents=[parent_parser], help="Execute post generation with modular flags")
    pipeline_parser.add_argument("--without", help="Comma-separated modules to skip (e.g. email,db,image)")
    pipeline_parser.add_argument("--with", dest="with_flags", help="Comma-separated modules to force enable (e.g. db,image)")
    pipeline_parser.add_argument("--prompt", help="Custom research prompt")

    # Subcommand: generate-image
    img_parser = subparsers.add_parser("generate-image", parents=[parent_parser], help="Generate an isolated image on-demand")
    img_parser.add_argument("--prompt", help="Text-to-image prompt for FLUX.1")
    img_parser.add_argument("--title", help="Article headline to automatically craft prompt from")
    img_parser.add_argument("--output", help="Custom output filepath on current machine")

    # Subcommand: cleanup-temp
    subparsers.add_parser("cleanup-temp", parents=[parent_parser], help="Purge server temporary image folder")

    args = parser.parse_args()

    server_url = args.server
    api_key = args.key

    if args.command == "status":
        handle_status(server_url, api_key, args)
    elif args.command == "pipeline":
        handle_pipeline(server_url, api_key, args)
    elif args.command == "generate-image":
        handle_generate_image(server_url, api_key, args)
    elif args.command == "cleanup-temp":
        handle_cleanup_temp(server_url, api_key, args)

if __name__ == "__main__":
    main()
