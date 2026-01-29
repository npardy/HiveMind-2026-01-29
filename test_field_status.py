"""
Test field_status.json reading and aggregation.
Creates mock data and verifies the aggregation logic works.
"""
import json
import os
import tempfile
import shutil

# Create a mock Data Sync structure
def create_mock_data_sync():
    """Create mock office-jobs structure with field_status.json files."""
    base = tempfile.mkdtemp(prefix="test_data_sync_")
    
    # Structure: office-jobs/26-000-050/26-001/26-001-260107/Field_Data/260107-0925AM/
    job_path = os.path.join(base, "26-000-050", "26-001", "26-001-260107")
    fd_path = os.path.join(job_path, "Field_Data")
    
    # Visit 1 - incomplete
    v1_path = os.path.join(fd_path, "260107-0925AM")
    os.makedirs(v1_path)
    with open(os.path.join(v1_path, "field_status.json"), 'w') as f:
        json.dump({
            "_schema_version": "1.0",
            "job_number": "26-001",
            "operator": "Joe",
            "job_type": "survey_rpr",
            "is_reupload": False,
            "time_spent": {"field_hours": 2.0, "travel_hours_oneway": 0.75},
            "field_work_done": False,
            "pins_found": "partial",
            "pins_placed": "no",
            "construction_tasks_completed": ["excavation_layout"],
            "notes": "Need to return for NE corner - access blocked",
            "qbo_sync": {"time_synced": False}
        }, f, indent=2)
    open(os.path.join(v1_path, "survey.csv"), 'w').close()
    
    # Visit 2 - re-upload (should be ignored)
    v2_path = os.path.join(fd_path, "260107-1130AM")
    os.makedirs(v2_path)
    with open(os.path.join(v2_path, "field_status.json"), 'w') as f:
        json.dump({
            "_schema_version": "1.0",
            "is_reupload": True,
            "replaces_folder": "260107-0925AM",
            "qbo_sync": {"time_synced": False}
        }, f, indent=2)
    open(os.path.join(v2_path, "survey.csv"), 'w').close()
    
    # Visit 3 - return trip, complete
    v3_path = os.path.join(fd_path, "260108-0800AM")
    os.makedirs(v3_path)
    with open(os.path.join(v3_path, "field_status.json"), 'w') as f:
        json.dump({
            "_schema_version": "1.0",
            "job_number": "26-001",
            "operator": "Allan",
            "job_type": "survey_rpr",
            "is_reupload": False,
            "time_spent": {"field_hours": 1.5, "travel_hours_oneway": 0.75},
            "field_work_done": True,
            "pins_found": "yes",
            "pins_placed": "yes",
            "construction_tasks_completed": ["excavation_layout"],
            "custom_tasks_completed": ["Septic layout"],
            "notes": "All complete, pins set",
            "qbo_sync": {"time_synced": False}
        }, f, indent=2)
    open(os.path.join(v3_path, "survey.csv"), 'w').close()
    
    return base

def test_aggregation():
    """Test aggregation logic."""
    mock_base = create_mock_data_sync()
    print(f"Created mock data at: {mock_base}")
    
    job_folder = os.path.join(mock_base, "26-000-050", "26-001", "26-001-260107")
    fd_path = os.path.join(job_folder, "Field_Data")
    
    field_uploads = []
    for fd_item in sorted(os.listdir(fd_path)):
        fd_item_path = os.path.join(fd_path, fd_item)
        if not os.path.isdir(fd_item_path):
            continue
        upload_entry = {"folder": fd_item}
        status_file = os.path.join(fd_item_path, "field_status.json")
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                upload_entry["field_status"] = json.load(f)
        field_uploads.append(upload_entry)
    
    print(f"\nFound {len(field_uploads)} uploads")
    
    # Aggregate - SAME LOGIC AS tool_executor.py
    aggregate = {
        "total_field_hours": 0,
        "total_travel_hours": 0,
        "visits": 0,
        "operators": set(),
        "construction_tasks": {},
        "custom_tasks": [],
        "needs_return_visit": False,
        "latest_notes": None,
        "unsynced_time_entries": 0,
        "pins_status": {"found": None, "placed": None}
    }
    
    for upload in field_uploads:
        fs = upload.get("field_status", {})
        if not fs or fs.get("is_reupload"):
            continue
        
        aggregate["visits"] += 1
        
        time_spent = fs.get("time_spent") or {}
        if time_spent.get("field_hours"):
            aggregate["total_field_hours"] += time_spent["field_hours"]
        if time_spent.get("travel_hours_oneway"):
            aggregate["total_travel_hours"] += time_spent["travel_hours_oneway"]
        
        if fs.get("operator"):
            aggregate["operators"].add(fs["operator"])
        
        for task in fs.get("construction_tasks_completed", []):
            aggregate["construction_tasks"][task] = aggregate["construction_tasks"].get(task, 0) + 1
        
        for task in fs.get("custom_tasks_completed", []):
            if task not in aggregate["custom_tasks"]:
                aggregate["custom_tasks"].append(task)
        
        qbo_sync = fs.get("qbo_sync") or {}
        if not qbo_sync.get("time_synced"):
            aggregate["unsynced_time_entries"] += 1
        
        if fs.get("notes"):
            aggregate["latest_notes"] = fs["notes"]
        
        if fs.get("pins_found"):
            aggregate["pins_status"]["found"] = fs["pins_found"]
        if fs.get("pins_placed"):
            aggregate["pins_status"]["placed"] = fs["pins_placed"]
        
        # Track latest field_work_done
        if fs.get("field_work_done") is not None:
            aggregate["_latest_field_work_done"] = fs["field_work_done"]
    
    # Check return visit based on LATEST status only
    if aggregate.get("_latest_field_work_done") == False:
        aggregate["needs_return_visit"] = True
    if aggregate["pins_status"]["placed"] in ["no", "partial"]:
        aggregate["needs_return_visit"] = True
    aggregate.pop("_latest_field_work_done", None)
    
    aggregate["operators"] = list(aggregate["operators"])
    
    print("\n=== FIELD SUMMARY ===")
    print(json.dumps(aggregate, indent=2))
    
    # Verify
    print("\n=== VERIFICATION ===")
    errors = []
    
    if aggregate["visits"] != 2:
        errors.append(f"visits: expected 2, got {aggregate['visits']}")
    else:
        print("OK visits: 2 (reupload excluded)")
    
    if aggregate["total_field_hours"] != 3.5:
        errors.append(f"field_hours: expected 3.5, got {aggregate['total_field_hours']}")
    else:
        print("OK total_field_hours: 3.5")
    
    if aggregate["total_travel_hours"] != 1.5:
        errors.append(f"travel_hours: expected 1.5, got {aggregate['total_travel_hours']}")
    else:
        print("OK total_travel_hours: 1.5")
    
    if set(aggregate["operators"]) != {"Joe", "Allan"}:
        errors.append(f"operators: expected Joe/Allan, got {aggregate['operators']}")
    else:
        print("OK operators: Joe, Allan")
    
    if aggregate["construction_tasks"].get("excavation_layout") != 2:
        errors.append(f"construction_tasks: expected excavation_layout x2, got {aggregate['construction_tasks']}")
    else:
        print("OK construction_tasks: excavation_layout x2")
    
    if aggregate["needs_return_visit"] != False:
        errors.append(f"needs_return_visit: expected False (latest is complete), got {aggregate['needs_return_visit']}")
    else:
        print("OK needs_return_visit: False (latest visit complete)")
    
    if aggregate["pins_status"]["placed"] != "yes":
        errors.append(f"pins_placed: expected yes, got {aggregate['pins_status']['placed']}")
    else:
        print("OK pins_status: placed=yes")
    
    shutil.rmtree(mock_base)
    
    if errors:
        print("\n=== ERRORS ===")
        for e in errors:
            print(f"  FAIL: {e}")
        return False
    else:
        print("\n=== ALL TESTS PASSED ===")
        return True

if __name__ == "__main__":
    success = test_aggregation()
    exit(0 if success else 1)
