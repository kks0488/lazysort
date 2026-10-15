import requests
import json
import os

BASE_URL = "http://localhost:2424"
SAMPLES_DIR = os.environ.get("LAZYSORT_TEST_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "samples"))

def print_step(step_name):
    print(f"\n{'='*20} {step_name} {'='*20}")

def test_scan():
    print_step("Step 1: Scan")
    url = f"{BASE_URL}/organize/scan"
    try:
        res = requests.post(url, json={"folder_path": SAMPLES_DIR})
        if res.status_code == 200:
            data = res.json()
            print(f"Duplicates: {len(data['duplicates'])}")
            print(f"Low Res: {len(data['low_res'])}")
            print(f"Screenshots: {len(data['screenshots'])}")
            print(f"Valid: {len(data['valid'])}")
            return data
        else:
            print(f"Error: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_cluster():
    print_step("Step 2: Cluster")
    url = f"{BASE_URL}/organize/cluster"
    try:
        res = requests.post(url, json={"folder_path": SAMPLES_DIR})
        if res.status_code == 200:
            clusters = res.json()
            print(f"Found {len(clusters)} clusters:")
            for c in clusters:
                print(f"  - {c['name']}: {len(c['files'])} files")
            return clusters
        else:
            print(f"Error: {res.status_code} - {res.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_execute(clusters):
    print_step("Step 3: Execute Moves")
    if not clusters:
        print("No clusters to execute.")
        return

    moves = []
    for cluster in clusters:
        # Target directory: samples/그룹/{ClusterName}
        target_dir = os.path.join(SAMPLES_DIR, "그룹", cluster['name'])
        
        for file_path in cluster['files']:
            filename = os.path.basename(file_path)
            dst = os.path.join(target_dir, filename)
            moves.append({"src": file_path, "dst": dst})
            
    print(f"Prepared {len(moves)} moves.")
    
    url = f"{BASE_URL}/organize/execute"
    try:
        res = requests.post(url, json={"moves": moves})
        if res.status_code == 200:
            print(f"Result: {res.json()}")
        else:
            print(f"Error: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    print(f"Testing Organizer on {SAMPLES_DIR}")
    
    scan_data = test_scan()
    if scan_data:
        clusters = test_cluster()
        if clusters:
            # Ask for confirmation before moving? No, just do it for the test as requested.
            test_execute(clusters)
