"""Deploy OMERO to Digital Ocean droplet with HTTPS via Caddy."""

import sys
import time
from pathlib import Path
from typing import Optional

import click
import paramiko
import yaml
from paramiko import SSHClient, AutoAddPolicy


def run_remote_command(
    ssh: SSHClient, command: str, check: bool = True
) -> tuple[str, str, int]:
    """Execute command on remote server."""
    print(f"Running: {command[:100]}...")
    stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
    exit_status = stdout.channel.recv_exit_status()

    out = stdout.read().decode("utf-8")
    err = stderr.read().decode("utf-8")

    if check and exit_status != 0:
        print(f"Command failed with exit code {exit_status}")
        print(f"STDOUT: {out}")
        print(f"STDERR: {err}")
        raise Exception(f"Command failed: {command[:100]}")

    return out, err, exit_status


def create_compose_config(domain: str) -> str:
    """Generate Docker Compose configuration for production."""
    return f"""services:
  # Caddy reverse proxy for HTTPS with automatic certificates
  caddy:
    image: lucaslorentz/caddy-docker-proxy:ci-alpine
    ports:
      - "80:80"
      - "443:443"
    environment:
      - CADDY_INGRESS_NETWORKS=caddy
    networks:
      - caddy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - caddy-data:/data
    restart: unless-stopped

  omero-db:
    image: postgres:16
    environment:
      POSTGRES_DB: omero
      POSTGRES_USER: omero
      POSTGRES_PASSWORD: omero
    networks:
      - omero-internal
    volumes:
      - omero-db-data:/var/lib/postgresql/data
    restart: unless-stopped

  omero-server:
    image: openmicroscopy/omero-server:latest
    depends_on:
      - omero-db
    environment:
      CONFIG_omero_db_user: omero
      CONFIG_omero_db_pass: omero
      CONFIG_omero_db_name: omero
      CONFIG_omero_db_host: omero-db
      ROOTPASS: omero
    networks:
      - omero-internal
    volumes:
      - omero-data:/OMERO
    ports:
      - "4063:4063"
      - "4064:4064"
    restart: unless-stopped

  omero-web:
    image: openmicroscopy/omero-web-standalone:latest
    depends_on:
      - omero-server
    environment:
      OMEROHOST: omero-server
      CONFIG_omero_web_csrf__trusted__origins: '["https://{domain}"]'
      CONFIG_omero_web_secure__proxy__ssl__header: '["HTTP_X_FORWARDED_PROTO", "https"]'
      CONFIG_omero_web_use__x__forwarded__host: "true"
    networks:
      - caddy
      - omero-internal
    labels:
      caddy: {domain}
      caddy.reverse_proxy: "{{{{upstreams 4080}}}}"
    restart: unless-stopped

  omero-iscc:
    image: ghcr.io/bio-codes/omero-iscc:latest
    depends_on:
      - omero-server
    environment:
      OMERO_ISCC_HOST: omero-server
      OMERO_ISCC_USER: root
      OMERO_ISCC_PASSWORD: omero
      OMERO_ISCC_POLL_SECONDS: 5
      OMERO_ISCC_PERSIST_DIR: /data
    networks:
      - omero-internal
    volumes:
      - ./iscc-data:/data
      - ./iscc-logs:/app/logs
    restart: unless-stopped

networks:
  caddy:
    external: true
  omero-internal:
    driver: bridge

volumes:
  omero-db-data:
  omero-data:
  caddy-data:
"""


def create_env_file() -> str:
    """Generate .env file for sensitive configuration."""
    return """# OMERO Configuration
POSTGRES_PASSWORD=omero
ROOTPASS=omero
"""


@click.command()
@click.option("--host", default="omero.iscc.id", help="Hostname or IP of the droplet")
@click.option("--user", default="root", help="SSH username")
@click.option("--domain", default="omero.iscc.id", help="Domain for HTTPS")
@click.option("--key-file", default=None, help="Path to SSH private key file")
@click.option("--password", default=None, help="SSH password (if not using key)")
def deploy(
    host: str, user: str, domain: str, key_file: Optional[str], password: Optional[str]
):
    """Deploy OMERO to Digital Ocean droplet."""
    print(f"🚀 Deploying OMERO to {host}")

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

        # Update system
        print("📦 Updating system packages...")
        run_remote_command(ssh, "apt-get update", check=False)

        # Install Docker if not present
        print("🐳 Checking Docker installation...")
        _, _, docker_check = run_remote_command(ssh, "command -v docker", check=False)

        if docker_check != 0:
            print("Installing Docker...")
            commands = [
                "apt-get install -y ca-certificates curl gnupg",
                "install -m 0755 -d /etc/apt/keyrings",
                "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
                "chmod a+r /etc/apt/keyrings/docker.gpg",
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null',
                "apt-get update",
                "apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
                "systemctl enable docker",
                "systemctl start docker",
            ]

            for cmd in commands:
                run_remote_command(ssh, cmd)
            print("✅ Docker installed")
        else:
            print("✅ Docker already installed")

        # Create deployment directory
        print("📁 Creating deployment directory...")
        run_remote_command(ssh, "mkdir -p /opt/omero")

        # Create external caddy network
        print("🌐 Creating external caddy network...")
        run_remote_command(
            ssh, "docker network create caddy 2>/dev/null || true", check=False
        )

        # Upload Docker Compose configuration
        print("📝 Creating Docker Compose configuration...")
        compose_content = create_compose_config(domain)

        # Write compose file
        sftp = ssh.open_sftp()
        with sftp.open("/opt/omero/compose.yaml", "w") as f:
            f.write(compose_content)

        # Write .env file
        with sftp.open("/opt/omero/.env", "w") as f:
            f.write(create_env_file())

        sftp.close()
        print("✅ Configuration files created")

        # Stop any existing containers
        print("🛑 Stopping any existing containers...")
        run_remote_command(ssh, "cd /opt/omero && docker compose down", check=False)

        # Start services
        print("🚀 Starting OMERO services...")
        run_remote_command(ssh, "cd /opt/omero && docker compose up -d")

        # Wait for services to be ready
        print("⏳ Waiting for services to start (this may take a few minutes)...")
        time.sleep(10)

        # Check service status
        print("📊 Checking service status...")
        out, _, _ = run_remote_command(ssh, "cd /opt/omero && docker compose ps")
        print(out)

        # Display access information
        print("\n" + "=" * 60)
        print("✅ OMERO deployment complete!")
        print("=" * 60)
        print(f"\n📌 Access your OMERO instance at:")
        print(f"   Web Interface: https://{domain}")
        print(f"   API/Insight:   {host}:4064")
        print(f"\n🔑 Default credentials:")
        print(f"   Username: root")
        print(f"   Password: omero")
        print(f"\n⚠️  Remember to change the default password!")
        print("\n📝 Useful commands (run on the server):")
        print("   View logs:    cd /opt/omero && docker compose logs -f")
        print("   Stop:         cd /opt/omero && docker compose down")
        print("   Restart:      cd /opt/omero && docker compose restart")
        print(
            "   Update:       cd /opt/omero && docker compose pull && docker compose up -d"
        )
        print("=" * 60)

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        sys.exit(1)
    finally:
        ssh.close()


if __name__ == "__main__":
    deploy()
