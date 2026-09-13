"""End-to-end API test verifying the 6-Specialist Agent system and routes."""
import json
import urllib.request
import urllib.error
import time

API_BASE = "http://127.0.0.1:8100/api"

def http_post(url, data=None, token=None):
    payload = json.dumps(data or {}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def http_get(url, token=None):
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def run_test():
    print("1. Creating test user...")
    username = f"spec_user_{int(time.time())}"
    email = f"{username}@example.com"
    password = "TestPassword123!"

    status, reg_res = http_post(f"{API_BASE}/auth/signup", {
        "name": username,
        "email": email,
        "password": password,
    })
    assert status == 200, f"Signup failed: {reg_res}"
    token = reg_res["token"]

    print("2. Checking /api/workflow/latest before assessment (NEVER_RUN)...")
    status, wf_latest = http_get(f"{API_BASE}/workflow/latest", token=token)
    assert status == 200
    assert "specialists_team" in wf_latest, "specialists_team missing from latest"
    team = wf_latest["specialists_team"]
    assert len(team) == 6, f"Expected 6 specialists, got {len(team)}"
    print(f"   Team size: {len(team)}. All 6 specialists present.")
    for s in team:
        print(f"   - {s['title']} -> {s['status']} ({s['status_label']})")

    print("3. Saving complete baseline assessment (3 checks)...")
    from tests.test_assessment_schema import valid_payload
    payload = valid_payload(sessionId=f"sess_{int(time.time())}")
    status, assess_res = http_post(f"{API_BASE}/assessments", payload, token=token)
    assert status == 201 or status == 200, f"Assessment save failed: {assess_res}"
    print("   Assessment saved successfully.")

    print("4. Checking /api/workflow/latest with completed assessment...")
    status, wf_after_assess = http_get(f"{API_BASE}/workflow/latest", token=token)
    assert status == 200
    team_after = wf_after_assess["specialists_team"]
    assert len(team_after) == 6
    print(f"   Team size after assessment: {len(team_after)}")

    print("5. Running workflow (POST /api/workflow/run)...")
    status, run_data = http_post(f"{API_BASE}/workflow/run", {}, token=token)
    assert status == 200
    assert "specialists_team" in run_data, "specialists_team missing from run response"
    team_run = run_data["specialists_team"]
    assert len(team_run) == 6, f"Expected 6 specialists, got {len(team_run)}"
    print("   Workflow run produced 6 specialists:")
    for s in team_run:
        print(f"   - {s['title']}: status={s['status']}, active={s.get('active')}, reason={s.get('reason')}")

    print("\n[SUCCESS] All 6-specialist backend assertions passed flawlessly!")

if __name__ == "__main__":
    run_test()
