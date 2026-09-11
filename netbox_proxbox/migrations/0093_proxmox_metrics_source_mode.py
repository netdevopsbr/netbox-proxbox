"""Add the persisted source policy for Proxmox metrics queries."""

from django.db import migrations, models


def _prepare_reverse(apps, _schema_editor) -> None:
    """Disable pull-only rows before the previous constraints are restored."""
    metrics_model = apps.get_model("netbox_proxbox", "ProxmoxMetricsInfluxDB")
    metrics_model.objects.filter(source_mode="pull", enabled=True).update(enabled=False)


class Migration(migrations.Migration):
    dependencies = [("netbox_proxbox", "0092_proxmox_metrics_plugin_credentials")]

    operations = [
        migrations.AddField(
            model_name="proxmoxmetricsinfluxdb",
            name="source_mode",
            field=models.CharField(
                choices=[
                    ("influx", "InfluxDB"),
                    ("pull", "Proxmox API pull"),
                    ("reconciled", "Reconciled InfluxDB and pull"),
                ],
                default="influx",
                help_text="Select InfluxDB, direct Proxmox API pull, or deterministic reconciliation.",
                max_length=16,
                verbose_name="Metrics source",
            ),
        ),
        migrations.AlterField(
            model_name="proxmoxmetricsinfluxdb",
            name="influx_url",
            field=models.URLField(
                blank=True,
                help_text="Credential-free InfluxDB base URL, for example https://influxdb.example:8086.",
                max_length=255,
                verbose_name="InfluxDB URL",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="proxmoxmetricsinfluxdb",
            name="netbox_proxbox_metrics_influxdb_query_token_configured",
        ),
        migrations.RemoveConstraint(
            model_name="proxmoxmetricsinfluxdb",
            name="netbox_proxbox_metrics_influxdb_url_is_safe",
        ),
        migrations.AddConstraint(
            model_name="proxmoxmetricsinfluxdb",
            constraint=models.CheckConstraint(
                condition=models.Q(source_mode="pull")
                | models.Q(query_token_enc__gt="")
                | models.Q(enabled=False),
                name="netbox_proxbox_metrics_influxdb_query_token_configured",
            ),
        ),
        migrations.AddConstraint(
            model_name="proxmoxmetricsinfluxdb",
            constraint=models.CheckConstraint(
                condition=models.Q(source_mode="pull")
                | models.Q(enabled=False)
                | models.Q(
                    influx_url__regex=r"^[Hh][Tt][Tt][Pp][Ss]://[^/?#@\s]+(?:/[^?#\s]*)?$"
                ),
                name="netbox_proxbox_metrics_influxdb_url_is_safe",
            ),
        ),
        migrations.RunPython(migrations.RunPython.noop, _prepare_reverse),
    ]
