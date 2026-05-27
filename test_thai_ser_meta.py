import subprocess, sys

# ติดตั้ง datasets ถ้ายังไม่มี
try:
    import datasets
except ImportError:
    print("Installing 'datasets' library...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets"])
    import datasets

from datasets import load_dataset

print("Loading THAI-SER in streaming mode (no full download)...")
ds = load_dataset("airesearch/thai-ser", split="train", streaming=True)

# ดึงแค่ 20 rows แรก
samples = list(ds.take(20))

if samples:
    print("\n=== Column Names ===")
    print(list(samples[0].keys()))

    print("\n=== Sample Rows (metadata only, no audio array) ===")
    for i, s in enumerate(samples[:5]):
        row = {k: v for k, v in s.items() if k != "audio"}
        print(f"[{i}] {row}")

    print("\n=== Unique Emotions in sample ===")
    emotions = set(s.get("emotion", "?") for s in samples)
    print(emotions)

    print("\n=== record_id examples ===")
    for s in samples[:5]:
        print(s.get("record_id", "N/A"))
else:
    print("No data returned.")
