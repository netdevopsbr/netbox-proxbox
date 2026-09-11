"""Keep saved storage selections while allowing an automatic fresh-install default."""

from django.db import migrations, models

from netbox_proxbox.choices import CredentialStorageBackendChoices


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_proxbox", "0093_proxmox_metrics_source_mode"),
    ]

    operations = [
        migrations.AlterField(
            model_name="proxboxpluginsettings",
            name="credential_storage_backend",
            field=models.CharField(
                blank=True,
                choices=CredentialStorageBackendChoices,
                default="",
                max_length=32,
                verbose_name="Credential storage backend",
                help_text=(
                    "Default storage for Proxmox API tokens, passwords, and SSH secrets. "
                    "Automatic uses OpenBao when netbox-openbao is enabled and legacy "
                    "encrypted storage otherwise. Explicit selections never fall back. "
                    "OpenBao is recommended for Write mode. Legacy encrypted storage "
                    "keeps Fernet-encrypted columns in NetBox."
                ),
            ),
        ),
    ]
