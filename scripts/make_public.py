#!/usr/bin/env python
"""Set up OMERO for public read access through the web interface."""

import omero
from omero.gateway import BlitzGateway
from omero.model import ExperimenterI, ExperimenterGroupI, PermissionsI
from omero.rtypes import rstring, rbool
import sys
import subprocess


def setup_public_access(host="localhost", root_password="omero"):
    """Create and configure public user for OMERO web access without login."""

    # Public user credentials - MUST match compose.yaml CONFIG values
    public_username = "public"
    public_password = "public"  # Must match compose.yaml
    public_group_name = "public_group"

    # Connect as root
    conn = BlitzGateway("root", root_password, host=host, port=4064, secure=True)

    try:
        if not conn.connect():
            print("Failed to connect to OMERO server")
            return False

        print("Connected as root")

        # Get admin service
        admin = conn.getAdminService()

        # Create public group with world-readable permissions (rwrwrw)
        try:
            existing_group = admin.lookupGroup(public_group_name)
            print(f"Group '{public_group_name}' already exists with ID: {existing_group.id.val}")
            public_group = existing_group
        except omero.ApiUsageException:
            print(f"Creating public group '{public_group_name}'...")
            public_group = ExperimenterGroupI()
            public_group.name = rstring(public_group_name)
            public_group.ldap = rbool(False)
            public_group.description = rstring("Public access group for login-free web viewing")

            # Set world-readable permissions (rwrwrw)
            perms = PermissionsI("rwrwrw")
            public_group.details.permissions = perms

            group_id = admin.createGroup(public_group)
            public_group = admin.getGroup(group_id)
            print(f"Created public group with ID: {group_id}")

        # Create public user
        public_user_exists = False
        try:
            existing_user = admin.lookupExperimenter(public_username)
            print(f"User '{public_username}' already exists with ID: {existing_user.id.val}")
            public_user_exists = True
            # Update password to ensure it matches
            admin.changePasswordWithOldPassword(rstring(public_password), rstring(public_password))
            print(f"Verified password for '{public_username}'")
        except omero.ApiUsageException:
            print(f"Creating public user '{public_username}'...")
            public_user = ExperimenterI()
            public_user.omeName = rstring(public_username)
            public_user.firstName = rstring("Public")
            public_user.lastName = rstring("User")
            public_user.email = rstring("public@localhost")
            public_user.ldap = rbool(False)

            # Add to public group and default user group
            groups = [public_group]
            try:
                user_group = admin.lookupGroup("user")
                groups.append(user_group)
            except:
                pass

            user_id = admin.createExperimenterWithPassword(
                public_user, rstring(public_password), public_group, groups
            )
            print(f"Created public user with ID: {user_id}")

        # Verify user can actually log in
        print(f"\nVerifying public user can authenticate...")
        test_conn = BlitzGateway(public_username, public_password, host=host, port=4064, secure=True)
        if test_conn.connect():
            print(f"✓ Public user '{public_username}' can authenticate successfully")
            test_conn.close()
        else:
            print(f"✗ WARNING: Public user '{public_username}' cannot authenticate!")
            print("  This may cause issues with public web access")

        print("\n" + "="*60)
        print("IMPORTANT: Web Configuration")
        print("="*60)
        print("\nThe public user has been created in OMERO server.")
        print("The compose.yaml already contains the necessary CONFIG_")
        print("environment variables for OMERO.web public access.")
        print("\nTo activate public access, restart the web container:")
        print("\n  docker compose restart omero-web")
        print("\nAfter restart, you should be able to access:")
        print("  http://localhost:4080")
        print("without being redirected to the login page.")
        print("\nPublic access credentials:")
        print(f"  Username: {public_username}")
        print(f"  Password: {public_password}")
        print(f"  Group: {public_group_name} (world-readable)")

        # Optionally restart the web container automatically
        print("\n" + "-"*60)
        response = input("Do you want to restart omero-web container now? (y/N): ")
        if response.lower() == 'y':
            try:
                print("Restarting omero-web container...")
                result = subprocess.run(
                    ["docker", "compose", "restart", "omero-web"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    print("✓ OMERO.web container restarted successfully")
                    print("\nPublic access should now be active!")
                    print("Try accessing: http://localhost:4080")
                else:
                    print(f"✗ Failed to restart container: {result.stderr}")
            except Exception as e:
                print(f"✗ Could not restart container: {e}")
                print("Please run manually: docker compose restart omero-web")

        return True

    except Exception as e:
        print(f"Error during setup: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()
        print("\nDisconnected from OMERO")


if __name__ == "__main__":
    success = setup_public_access()
    sys.exit(0 if success else 1)