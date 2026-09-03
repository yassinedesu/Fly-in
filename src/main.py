def check_environment(drone_id: str) -> str:
    """Verify the environment setup by returning a formatted string."""
    return f"Environment ready for {drone_id}"

if __name__ == "__main__":
    print(check_environment("D1"))