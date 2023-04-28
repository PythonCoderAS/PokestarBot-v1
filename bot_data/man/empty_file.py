import os

path = os.path.dirname(__file__)

for file in sorted(filter(lambda filename: filename.endswith(".md"), os.listdir(path))):
    with open(os.path.join(path, file), "r") as f:
        data = f.read().splitlines(False)
        if not data or not data[0]:
            print(f"File {os.path.join(path, file)} is not complete.")
