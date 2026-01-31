"""Modal image definition for DevLabo sandbox containers."""

import modal

# Define the sandbox image with all required tooling
sandbox_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "curl",
        "git",
        "ca-certificates",
        "gnupg",
    )
    .run_commands(
        # Install Node.js 20.x via NodeSource
        "mkdir -p /etc/apt/keyrings",
        "curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg",
        'echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list',
        "apt-get update",
        "apt-get install -y nodejs",
        # Install pnpm globally
        "npm install -g pnpm",
        # Install global dev tools
        "npm install -g vite vitest create-vite",
    )
    .pip_install(
        "boto3>=1.34.0",
        "watchdog>=4.0.0",
    )
    .env(
        {
            # Set pnpm store location
            "PNPM_HOME": "/root/.local/share/pnpm",
            # Ensure Node.js uses UTF-8
            "NODE_OPTIONS": "--max-old-space-size=4096",
        }
    )
)

# Create Modal app for testing the image
app = modal.App("devlabo-sandbox-image-test")


@app.function(image=sandbox_image)
def test_image():
    """Test function to verify the sandbox image is correctly configured."""
    import subprocess

    results = {}

    # Check Python version
    python_result = subprocess.run(
        ["python", "--version"], capture_output=True, text=True
    )
    results["python"] = python_result.stdout.strip() or python_result.stderr.strip()

    # Check Node.js version
    node_result = subprocess.run(["node", "--version"], capture_output=True, text=True)
    results["node"] = node_result.stdout.strip()

    # Check npm version
    npm_result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
    results["npm"] = npm_result.stdout.strip()

    # Check pnpm version
    pnpm_result = subprocess.run(["pnpm", "--version"], capture_output=True, text=True)
    results["pnpm"] = pnpm_result.stdout.strip()

    # Check vite version
    vite_result = subprocess.run(
        ["vite", "--version"], capture_output=True, text=True
    )
    results["vite"] = vite_result.stdout.strip()

    # Check vitest is installed
    vitest_result = subprocess.run(
        ["vitest", "--version"], capture_output=True, text=True
    )
    results["vitest"] = vitest_result.stdout.strip() or "installed"

    # Check boto3 is importable
    try:
        import boto3
        results["boto3"] = boto3.__version__
    except ImportError as e:
        results["boto3"] = f"ERROR: {e}"

    # Check watchdog is importable
    try:
        import watchdog
        results["watchdog"] = watchdog.__version__
    except ImportError as e:
        results["watchdog"] = f"ERROR: {e}"

    return results


@app.local_entrypoint()
def main():
    """Entry point for testing the image via `modal run sandbox/image.py`."""
    print("Testing DevLabo sandbox image...")
    print("-" * 40)

    results = test_image.remote()

    for tool, version in results.items():
        print(f"{tool:12} : {version}")

    print("-" * 40)
    print("Image test complete!")
