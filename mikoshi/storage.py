import os


def get_persistent_storage(data_dir, tool_server_name):
    storage_dir = os.path.join(data_dir, "tool_storage", tool_server_name)
    os.makedirs(storage_dir, exist_ok=True)
    return storage_dir
