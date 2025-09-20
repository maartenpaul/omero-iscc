#!/usr/bin/env python
"""Set up OMERO for public read access through the web interface."""

import logging
import omero
from omero.gateway import BlitzGateway
from omero.model import ExperimenterI, ExperimenterGroupI, PermissionsI
from omero.rtypes import rstring, rbool
import sys

# Suppress expected warnings
logging.getLogger("omero.gateway").setLevel(logging.ERROR)


def setup_public_access(host="localhost", root_password="omero"):
    """Create and configure public user for OMERO web access."""

    # Public user credentials - MUST match compose.yaml CONFIG values
    public_username = "public"
    public_password = "public"
    public_group_name = "public_group"

    # Connect as root
    conn = BlitzGateway("root", root_password, host=host, port=4064, secure=True)

    try:
        if not conn.connect():
            print("Failed to connect to OMERO server")
            return False

        print("Connected as root")
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
            public_group.description = rstring("Public access group for web viewing")

            # Set world-readable permissions (rwrwrw)
            perms = PermissionsI("rwrwrw")
            public_group.details.permissions = perms

            group_id = admin.createGroup(public_group)
            public_group = admin.getGroup(group_id)
            print(f"Created public group with ID: {group_id}")

        # Create or update public user
        try:
            existing_user = admin.lookupExperimenter(public_username)
            print(f"User '{public_username}' already exists with ID: {existing_user.id.val}")

            # Ensure public user is member of public_group
            user_groups = admin.containedGroups(existing_user.id.val)
            group_ids = [g.id.val for g in user_groups]

            if public_group.id.val not in group_ids:
                print(f"Adding existing user to public_group...")
                admin.addGroups(existing_user, [public_group])

            # Set public_group as default group
            admin.setDefaultGroup(existing_user, public_group)
            print(f"Set public_group as default for existing user")

            # Note: We cannot reset the password for an existing user
            print(f"Note: Using existing password for user '{public_username}'")

        except omero.ApiUsageException:
            print(f"Creating public user '{public_username}'...")
            public_user = ExperimenterI()
            public_user.omeName = rstring(public_username)
            public_user.firstName = rstring("Public")
            public_user.lastName = rstring("User")
            public_user.email = rstring("public@localhost")
            public_user.ldap = rbool(False)

            # Get the default "user" group that all users should belong to
            groups = [public_group]
            try:
                user_group = admin.lookupGroup("user")
                groups.append(user_group)
                print(f"Adding to default 'user' group")
            except:
                pass

            # Create user with public_group as primary/default group
            # but also member of 'user' group for authentication
            user_id = admin.createExperimenterWithPassword(
                public_user, rstring(public_password), public_group, groups
            )
            print(f"Created public user with ID: {user_id}")

        # Verify authentication
        print(f"\nVerifying public user can authenticate...")
        test_conn = BlitzGateway(public_username, public_password, host=host, port=4064, secure=True)
        if test_conn.connect():
            print(f"✓ Public user can authenticate successfully")
            test_conn.close()
        else:
            print(f"✗ WARNING: Public user cannot authenticate!")

        print("\n" + "=" * 60)
        print("SUCCESS: Public Access Configured")
        print("=" * 60)
        print("\nPublic access is now active at: http://localhost:4080")
        print(f"Username: {public_username}, Password: {public_password}")

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