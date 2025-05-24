import os

# Define profile names without storing keys. Users will be prompted for actual keys.
# These names are just for user convenience to remember different configurations.
ENV_PROFILE_NAMES = ["dev", "prod", "test", "custom_profile"]

def switch_env(profile_name_to_set):
    # Ensure the chosen profile name is either one of the predefined or the user confirms a custom name.
    if profile_name_to_set not in ENV_PROFILE_NAMES:
        print(f"Warning: '{profile_name_to_set}' is not a predefined profile name ({', '.join(ENV_PROFILE_NAMES)}).")
        confirm_custom = input(f"Do you want to proceed and create a .env file for a new profile named '{profile_name_to_set}'? (y/n): ").lower()
        if confirm_custom != 'y':
            print("Operation cancelled by user.")
            return

    print(f"\nConfiguring .env for profile: '{profile_name_to_set}'")

    # Prompt for LLAMA_CLOUD_API_KEY
    llama_api_key = input("Enter the LLAMA_CLOUD_API_KEY: ").strip()
    if not llama_api_key.startswith("llama-cloud-") or not llama_api_key:
        print("Invalid or empty LLAMA_CLOUD_API_KEY format. Key should start with 'llama-cloud-'.")
        print("Operation cancelled.")
        return

    # Prompt for OPENAI_API_KEY
    openai_api_key = input("Enter the OPENAI_API_KEY (optional, press Enter to skip if not needed for this profile): ").strip()
    if openai_api_key and (not openai_api_key.startswith("sk-") and not openai_api_key.startswith("org-")): # Basic check
        print("Warning: The OpenAI API key format seems unusual but proceeding.")


    try:
        with open(".env", "w") as f:
            f.write(f"# Environment configuration for profile: {profile_name_to_set}\n")
            f.write(f"LLAMA_CLOUD_API_KEY={llama_api_key}\n")
            if openai_api_key:
                f.write(f"OPENAI_API_KEY={openai_api_key}\n")
            else:
                f.write("# OPENAI_API_KEY is not set for this profile\n")
        print(f"\nSuccessfully configured and saved to .env for profile '{profile_name_to_set}'.")
        if not openai_api_key:
            print("Note: OPENAI_API_KEY was not provided and is not set in the .env file.")

    except IOError as e:
        print(f"Error writing to .env file: {e}")

def show_profiles():
    print("\nThis script helps you create or update the .env file with API keys.")
    print("You can manage configurations for different named profiles (e.g., dev, prod).")
    print("Predefined profile name suggestions (you can also use a new custom name):")
    for name in ENV_PROFILE_NAMES:
        print(f"  - {name}")

if __name__ == "__main__":
    show_profiles()
    chosen_profile = input("\nEnter a profile name to configure (e.g., dev, prod, or a new custom name): ").strip()

    if chosen_profile:
        switch_env(chosen_profile)
    else:
        print("No profile name entered. Exiting.")
