import os


def count_appmaps():
    count = 0
    for root, _, files in os.walk("tmp/appmap"):
        for file in files:
            if file.endswith(".appmap.json"):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                if 10 * 1024 <= file_size < 40 * 1024 * 1024:
                    count += 1
    return count

