# Generated by Django 3.1.7 on 2021-07-13 23:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mathesar', '0010_database'),
    ]

    operations = [
        migrations.AddField(
            model_name='schema',
            name='database_link',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='schemas', to='mathesar.database'),
        ),
    ]