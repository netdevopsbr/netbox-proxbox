# Generated by Django 3.1.8 on 2021-04-19 01:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('virtualization', '0019_standardize_name_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='VmResources',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('node', models.CharField(blank=True, max_length=64)),
                ('proxmox_vm_id', models.PositiveIntegerField()),
                ('vcpus', models.PositiveIntegerField()),
                ('memory', models.PositiveIntegerField()),
                ('disk', models.PositiveIntegerField()),
                ('status', models.CharField(default='active', max_length=50)),
                ('type', models.CharField(blank=True, max_length=64)),
                ('cluster', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='virtualization.cluster')),
                ('virtual_machine', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='virtualization.virtualmachine')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
