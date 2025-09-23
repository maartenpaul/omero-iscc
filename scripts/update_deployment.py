"""Update existing OMERO deployment with omero-iscc service."""

import sys
import time
from pathlib import Path
from typing import Optional

import click
import paramiko
from paramiko import SSHClient, AutoAddPolicy
from deploy import create_compose_config, run_remote_command


@click.command()
@click.option("--host", default="omero.iscc.id", help="Hostname or IP of the droplet")
@click.option("--user", default="root", help="SSH username")
@click.option("--domain", default="omero.iscc.id", help="Domain for HTTPS")
@click.option("--key-file", default=None, help="Path to SSH private key file")
@click.option("--password", default=None, help="SSH password (if not using key)")
def update_deployment(
    host: str, user: str, domain: str, key_file: Optional[str], password: Optional[str]
):
    """Update existing OMERO deployment to include omero-iscc service."""
    print(f"🚀 Updating OMERO deployment at {host}")

    # Initialize SSH client
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())

    try:
        # Connect to server
        print(f"📡 Connecting to {user}@{host}...")
        connect_kwargs = {"hostname": host, "username": user, "timeout": 30}

        if key_file:
            key_path = Path(key_file).expanduser()
            if key_path.exists():
                connect_kwargs["key_filename"] = str(key_path)
            else:
                print(f"Warning: Key file {key_file} not found, trying default keys")

        if password:
            connect_kwargs["password"] = password

        ssh.connect(**connect_kwargs)
        print("✅ Connected successfully")

        # Backup current compose file
        print("💾 Backing up current configuration...")
        run_remote_command(
            ssh,
            "cp /opt/omero/compose.yaml /opt/omero/compose.yaml.backup",
            check=False
        )

        # Update Docker Compose configuration
        print("📝 Updating Docker Compose configuration...")
        compose_content = create_compose_config(domain)

        # Write new compose file
        sftp = ssh.open_sftp()
        with sftp.open("/opt/omero/compose.yaml", "w") as f:
            f.write(compose_content)
        sftp.close()
        print("✅ Configuration updated")

        # Pull the omero-iscc image
        print("🐳 Pulling omero-iscc image...")
        run_remote_command(
            ssh,
            "docker pull ghcr.io/bio-codes/omero-iscc:latest"
        )

        # Apply the update without downtime
        print("🔄 Applying update to services...")
        run_remote_command(
            ssh,
            "cd /opt/omero && docker compose up -d --remove-orphans"
        )

        # Wait for services to stabilize
        print("⏳ Waiting for services to stabilize...")
        time.sleep(10)

        # Check service status
        print("📊 Checking service status...")
        out, _, _ = run_remote_command(
            ssh,
            "cd /opt/omero && docker compose ps"
        )
        print(out)

        # Check omero-iscc logs
        print("\n📋 Checking omero-iscc service logs...")
        out, _, _ = run_remote_command(
            ssh,
            "cd /opt/omero && docker compose logs omero-iscc --tail=20",
            check=False
        )
        print(out)

        # Display completion information
        print("\n" + "=" * 60)
        print("✅ Deployment update complete!")
        print("=" * 60)
        print(f"\n🎉 The omero-iscc service has been added to your deployment")
        print(f"\n📌 Services running at:")
        print(f"   Web Interface: https://{domain}")
        print(f"   API/Insight:   {host}:4064")
        print(f"\n📝 Useful commands:")
        print("   View omero-iscc logs:  ssh root@omero.iscc.id 'cd /opt/omero && docker compose logs -f omero-iscc'")
        print("   Check all services:    ssh root@omero.iscc.id 'cd /opt/omero && docker compose ps'")
        print("   Restart omero-iscc:    ssh root@omero.iscc.id 'cd /opt/omero && docker compose restart omero-iscc'")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Update failed: {e}")
        print("\n🔙 You can restore the backup with:")
        print(f"   ssh {user}@{host} 'mv /opt/omero/compose.yaml.backup /opt/omero/compose.yaml && cd /opt/omero && docker compose up -d'")
        sys.exit(1)
    finally:
        ssh.close()


if __name__ == "__main__":
    update_deployment()