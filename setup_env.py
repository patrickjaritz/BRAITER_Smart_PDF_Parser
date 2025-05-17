import os

def create_env_file(api_key, filename=".env"):
    with open(filename, "w") as f:
        f.write(f"LLAMA_CLOUD_API_KEY={api_key.strip()}\n")
    print(f".env file created with your API key stored safely in {filename}.")

if __name__ == "__main__":
    key = input("Paste your LlamaParse API key (starts with 'llama-cloud-'): ").strip()
    create_env_file(key)
