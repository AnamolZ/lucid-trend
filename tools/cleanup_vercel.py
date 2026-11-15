import os
import time
import requests

# Vercel Credentials (reads from environment variables if present, e.g. in GitHub Actions)
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN")
PROJECT_ID = os.environ.get("PROJECT_ID", os.environ.get("VERCEL_PROJECT_ID", "prj_MYQrtebnpkCeBCQbud3CmA5yLJyW"))

# Number of latest successful production deployments to keep (1 = active only, 2 = active + 1 rollback backup)
KEEP_PRODUCTION_COUNT = int(os.environ.get("KEEP_PRODUCTION_COUNT", 2))

headers = {
    "Authorization": f"Bearer {VERCEL_TOKEN}",
    "Content-Type": "application/json"
}

def get_active_production_info(project_id, headers):
    """
    Fetch the currently active production deployment ID and protected aliases
    directly from the Vercel Project API to ensure the live site is never touched.
    """
    protected_ids = set()
    active_prod_id = None
    
    # 1. Check Project details for target production deployment ID
    proj_res = requests.get(f"https://api.vercel.com/v9/projects/{project_id}", headers=headers)
    if proj_res.status_code == 200:
        proj_data = proj_res.json()
        prod_target = proj_data.get("targets", {}).get("production", {})
        active_prod_id = prod_target.get("id")
        if active_prod_id:
            protected_ids.add(active_prod_id)
            print(f"Active live production deployment: {active_prod_id}")
            print(f"Active production URL: {prod_target.get('url')}")
    else:
        print(f"Warning: Could not fetch project target details ({proj_res.status_code}): {proj_res.text}")
    
    # 2. Check Aliases for production domain mappings (e.g. custom domains)
    alias_res = requests.get(f"https://api.vercel.com/v4/aliases?projectId={project_id}", headers=headers)
    if alias_res.status_code == 200:
        aliases = alias_res.json().get("aliases", [])
        for a in aliases:
            alias_name = a.get("alias", "")
            dep_id = a.get("deploymentId")
            # Protect deployments associated with main/production domains
            if dep_id and not ("git-redesign" in alias_name or "git-application" in alias_name):
                protected_ids.add(dep_id)
                print(f"Protecting aliased deployment: {dep_id} ({alias_name})")
    
    return active_prod_id, protected_ids

def determine_protected_deployments(all_deployments, active_prod_id, base_protected_ids, keep_count):
    """
    Determine which deployments to protect based on KEEP_PRODUCTION_COUNT.
    Protects:
      1. The current live production deployment
      2. The (keep_count - 1) most recent successful production builds as rollback backups
      3. Any active custom domain aliases
    """
    protected_ids = set(base_protected_ids)
    
    # Filter production deployments that finished successfully (READY)
    prod_ready_deps = [
        d for d in all_deployments
        if d.get("target") == "production" and d.get("state") in ("READY", "ready")
    ]
    # Sort descending by creation timestamp (newest first)
    prod_ready_deps.sort(key=lambda d: d.get("created", 0), reverse=True)
    
    # Ensure active_prod_id is first if present
    if active_prod_id:
        active_deps = [d for d in prod_ready_deps if d.get("uid") == active_prod_id]
        other_deps = [d for d in prod_ready_deps if d.get("uid") != active_prod_id]
        prod_ready_deps = active_deps + other_deps
    
    # Select the top N production deployments to preserve
    preserved = prod_ready_deps[:keep_count]
    print(f"\n[RETENTION POLICY] Preserving top {len(preserved)} production deployment(s) (Target: {keep_count}):")
    for i, d in enumerate(preserved, start=1):
        uid = d.get("uid")
        protected_ids.add(uid)
        role = "CURRENT LIVE PRODUCTION" if uid == active_prod_id else f"ROLLBACK BACKUP #{i-1}"
        print(f"  [{i}] {uid} - {role} ({d.get('url')})")
        
    return protected_ids

def fetch_all_deployments(project_id, headers):
    """Fetch all deployments across all pages using pagination."""
    all_deployments = []
    until = None
    page = 1
    
    print("\nFetching deployments from Vercel API...")
    while True:
        url = f"https://api.vercel.com/v6/deployments?projectId={project_id}&limit=100"
        if until:
            url += f"&until={until}"
        
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"Error fetching page {page}: {res.status_code} {res.text}")
            break
        
        data = res.json()
        deployments = data.get("deployments", [])
        if not deployments:
            break
        
        all_deployments.extend(deployments)
        print(f"  Page {page}: fetched {len(deployments)} deployments (total so far: {len(all_deployments)})")
        
        pagination = data.get("pagination", {})
        next_until = pagination.get("next")
        if not next_until or next_until == until:
            break
        
        until = next_until
        page += 1
        time.sleep(0.1)  # Brief pause between pagination requests
        
    return all_deployments

def delete_deployment(dep_id, headers, max_retries=3):
    """Delete a single deployment with retry logic for rate limits."""
    url = f"https://api.vercel.com/v13/deployments/{dep_id}"
    for attempt in range(max_retries):
        del_response = requests.delete(url, headers=headers)
        
        if del_response.status_code == 200:
            return True, "Deleted successfully"
        elif del_response.status_code == 429:
            # Rate limited; back off and retry
            wait_time = 2 * (attempt + 1)
            print(f"Rate limited on {dep_id}. Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            continue
        else:
            return False, f"HTTP {del_response.status_code}: {del_response.text}"
            
    return False, "Exceeded max retries due to rate limiting"

def wait_for_in_progress_builds(project_id, headers, max_wait_seconds=60):
    """
    If a deployment was just triggered (e.g. via git push in CI/CD), wait for it
    to finish building before evaluating which deployments to keep.
    """
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        try:
            res = requests.get(f"https://api.vercel.com/v6/deployments?projectId={project_id}&limit=5", headers=headers)
            if res.status_code == 200:
                deps = res.json().get("deployments", [])
                in_progress = [d for d in deps if d.get("state") in ("BUILDING", "INITIALIZING", "QUEUED")]
                if in_progress:
                    dep = in_progress[0]
                    print(f"Deployment {dep.get('uid')} is {dep.get('state')}. Waiting for build to complete ({int(time.time() - start_time)}s elapsed)...")
                    time.sleep(5)
                    continue
        except Exception as e:
            print(f"Warning checking in-progress builds: {e}")
        break

def main():
    if not VERCEL_TOKEN:
        print("\n[ERROR] VERCEL_TOKEN environment variable is not set! Please configure it in your GitHub Secrets or environment.")
        return

    print("="*60)
    print(f"VERCEL CLEANUP SCRIPT (Retention: {KEEP_PRODUCTION_COUNT} Production Deployments)")
    print("="*60)
    
    # If run in CI/CD right after git push, wait for any in-flight build to finalize
    wait_for_in_progress_builds(PROJECT_ID, headers)
    
    active_prod_id, base_protected_ids = get_active_production_info(PROJECT_ID, headers)
    
    if not active_prod_id and not base_protected_ids:
        print("\n[SAFETY ABORT] Could not identify active production deployment! Aborting to prevent accidental deletion.")
        return
    
    deployments = fetch_all_deployments(PROJECT_ID, headers)
    total_found = len(deployments)
    print(f"Total deployments found: {total_found}")

    
    # Calculate protected IDs including the rollback backups
    protected_ids = determine_protected_deployments(
        deployments, 
        active_prod_id, 
        base_protected_ids, 
        keep_count=KEEP_PRODUCTION_COUNT
    )
    
    deleted_count = 0
    skipped_count = 0
    failed_count = 0
    
    print("\nProcessing deployments:")
    for idx, dep in enumerate(deployments, start=1):
        dep_id = dep.get("uid")
        target = dep.get("target")
        state = dep.get("state")
        url = dep.get("url")
        
        # SAFETY CHECK: Skip active production and rollback backup deployments
        if dep_id in protected_ids:
            role = "CURRENT LIVE" if dep_id == active_prod_id else "ROLLBACK BACKUP"
            print(f"[{idx}/{total_found}] [PROTECTED: {role}] Skipping: {dep_id} ({url})")
            skipped_count += 1
            continue
        
        # Delete old deployment (older production build, preview, canceled, error)
        print(f"[{idx}/{total_found}] Deleting old deployment ({target or 'preview'}, {state}): {dep_id} ...", end=" ", flush=True)
        success, message = delete_deployment(dep_id, headers)
        
        if success:
            print("OK")
            deleted_count += 1
        else:
            print(f"FAILED ({message})")
            failed_count += 1
            
        time.sleep(0.15)  # Respect rate limits
    
    print("\n" + "="*50)
    print("CLEANUP SUMMARY")
    print(f"Total deployments scanned: {total_found}")
    print(f"Deployments kept safe (Live + Rollback): {skipped_count}")
    print(f"Old deployments successfully deleted: {deleted_count}")
    print(f"Deployments failed to delete: {failed_count}")
    print("="*50)

if __name__ == "__main__":
    main()

