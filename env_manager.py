import os

ENV_PROFILES = {
    "dev": "llama-cloud-abc123_dev",
    "prod": "llama-cloud-xyz456_prod",
    "test": "llama-cloud-test789"
}

def switch_env(profile_name):
    key = ENV_PROFILES.get(profile_name)
    if not key:
        print("Profile not found.")
        return
    with open(".env", "w") as f:
        f.write(f"LLAMA_CLOUD_API_KEY={key}\n")
    print(f"Switched to '{profile_name}' profile.")

def show_profiles():
    print("Available profiles:")
    for name in ENV_PROFILES:
        print(f"  - {name}")

if __name__ == "__main__":
    show_profiles()
    profile = input("Enter profile to use: ").strip()
    switch_env(profile)
